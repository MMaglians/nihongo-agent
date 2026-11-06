"""Trascrizione degli appunti scritti a mano (PDF di Goodnotes) in Markdown, con elenco dei dubbi."""
import io
import json
import re
import time
from pathlib import Path

from google.genai import errors, types
from pydantic import BaseModel
from pypdf import PdfReader, PdfWriter

from nihongo_agent.retry import generate_with_retry

MAX_INLINE_BYTES = 18 * 1024 * 1024  # sotto il limite di circa 20 MB per i file inviati direttamente

PROMPT = """Trascrivi FEDELMENTE queste pagine di appunti scritti a mano (studio del giapponese).
Regole:
- Scrivi esattamente ciò che è scritto: NON correggere, NON completare, NON tradurre.
- Il giapponese è scritto quasi sempre in romaji: lascialo in romaji, non convertirlo in kana o kanji.
  Kana e kanji presenti vanno trascritti così come sono.
- Usa Markdown: un titolo '# ' per ogni argomento o lezione che riconosci, '## ' per i sottoargomenti,
  elenchi puntati per gli elenchi, tabelle Markdown per le tabelle.
- Se una parola non si legge, scrivi [illeggibile]. Non indovinare.
- Inizia ogni pagina con la riga <!-- pagina N --> (N = numero di pagina indicato nella richiesta).
In "doubts" elenca i punti in cui l'appunto sembra contenere un errore o una parola mancante
(per esempio una frase incompleta o una coniugazione sospetta): pagina, testo, problema.
Non correggere questi punti nel Markdown: segnalali soltanto."""


class Doubt(BaseModel):
    page: int
    text: str
    issue: str


class Transcription(BaseModel):
    markdown: str
    doubts: list[Doubt]


def page_blocks(n_pages: int, size: int) -> list[tuple[int, int]]:
    """Blocchi (primo, ultimo) numerati da 1, es. 12 pagine a blocchi di 5 -> (1,5) (6,10) (11,12)."""
    return [(start, min(start + size - 1, n_pages)) for start in range(1, n_pages + 1, size)]


def extract_pages(reader: PdfReader, first: int, last: int) -> bytes:
    writer = PdfWriter()
    for i in range(first - 1, last):
        writer.add_page(reader.pages[i])
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def transcribe_block(client, model: str, pdf_bytes: bytes, first: int, last: int) -> Transcription:
    config = types.GenerateContentConfig(
        response_mime_type="application/json", response_schema=Transcription, temperature=0
    )
    contents = [
        types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
        f"{PROMPT}\n\nQueste sono le pagine da {first} a {last} del quaderno.",
    ]
    response = generate_with_retry(client, model=model, contents=contents, config=config)
    return Transcription.model_validate_json(response.text or "")


def fix_page_numbers(result: Transcription, first: int, last: int) -> Transcription:
    """Il modello a volte numera le pagine del blocco da 1: le riporta ai numeri del quaderno."""
    size, offset = last - first + 1, first - 1
    if offset == 0:
        return result
    fix = lambda n: n + offset if 1 <= n <= size else n  # noqa: E731
    markdown = re.sub(r"<!-- pagina (\d+) -->", lambda m: f"<!-- pagina {fix(int(m.group(1)))} -->",
                      result.markdown)
    doubts = [d.model_copy(update={"page": fix(d.page)}) for d in result.doubts]
    return Transcription(markdown=markdown, doubts=doubts)


def write_review_list(out_dir: Path) -> Path:
    """Raccoglie tutti i dubbi in REVISIONE.md, una lista di controllo da spuntare."""
    lines = ["# Revisione degli appunti trascritti", ""]
    for path in sorted(out_dir.glob("*.doubts.json")):
        doubts = json.loads(path.read_text(encoding="utf-8"))
        md_name = path.name.replace(".doubts.json", ".md")
        lines.append(f"## {md_name}")
        lines += [f"- [ ] p. {d['page']}: \"{d['text']}\" — {d['issue']}" for d in doubts] or ["- nessun dubbio segnalato"]
        lines.append("")
    review = out_dir / "REVISIONE.md"
    review.write_text("\n".join(lines), encoding="utf-8")
    return review


def transcribe_pdf(client, model: str, pdf_path: Path, out_dir: Path, *, pages_per_block: int = 5,
                   first_page: int = 1, last_page: int | None = None, pause: float = 15.0,
                   sleep=time.sleep, log=print) -> list[Path]:
    """Trascrive il PDF a blocchi. Salta i blocchi già fatti: se si interrompe, basta rilanciarlo."""
    reader = PdfReader(str(pdf_path))
    last_page = min(last_page or len(reader.pages), len(reader.pages))
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for first, last in page_blocks(last_page - first_page + 1, pages_per_block):
        first, last = first + first_page - 1, last + first_page - 1
        target = out_dir / f"{pdf_path.stem}_p{first:03d}-{last:03d}.md"
        if target.exists():
            log(f"  p. {first}-{last}: già trascritte, salto")
            continue
        data = extract_pages(reader, first, last)
        if len(data) > MAX_INLINE_BYTES:
            raise ValueError(f"p. {first}-{last}: {len(data) / 1e6:.0f} MB, troppo grande: "
                             "usa --pages-per-block più piccolo")
        try:
            result = transcribe_block(client, model, data, first, last)
        except errors.ClientError as exc:
            if exc.code != 429:
                raise
            log("  quota al minuto superata: attendo 60 s e riprovo una volta")
            sleep(60)
            result = transcribe_block(client, model, data, first, last)
        result = fix_page_numbers(result, first, last)
        target.write_text(result.markdown.strip() + "\n", encoding="utf-8")
        target.with_name(target.stem + ".doubts.json").write_text(
            json.dumps([d.model_dump() for d in result.doubts], ensure_ascii=False, indent=2),
            encoding="utf-8")
        log(f"  p. {first}-{last}: {len(result.markdown)} caratteri, {len(result.doubts)} dubbi")
        written.append(target)
        sleep(pause)
    write_review_list(out_dir)
    return written