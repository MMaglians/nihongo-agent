"""Trascrive un PDF di appunti in Markdown.

Uso:  uv run python scripts/transcribe_notes.py raw_notes/quaderno.pdf --first 1 --last 5
I file vanno in notes_draft/ (privata). Dopo la revisione li sposti a mano in notes/.
"""
import argparse
from pathlib import Path

from google import genai

from nihongo_agent.config import get_api_key, get_model_name
from nihongo_agent.transcribe import transcribe_pdf

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Trascrizione degli appunti scritti a mano")
    parser.add_argument("pdf", type=Path, help="PDF esportato da Goodnotes")
    parser.add_argument("--first", type=int, default=1, help="prima pagina (da 1)")
    parser.add_argument("--last", type=int, default=None, help="ultima pagina (default: fine)")
    parser.add_argument("--pages-per-block", type=int, default=5)
    parser.add_argument("--model", default=None, help="modello (default: GEMINI_MODEL del .env)")
    parser.add_argument("--out", type=Path, default=ROOT / "notes_draft")
    args = parser.parse_args()

    client = genai.Client(api_key=get_api_key())
    model = args.model or get_model_name()
    print(f"Trascrivo {args.pdf.name} con {model} in {args.out}")
    written = transcribe_pdf(client, model, args.pdf, args.out, pages_per_block=args.pages_per_block,
                             first_page=args.first, last_page=args.last)
    print(f"Fatto: {len(written)} file nuovi. Dubbi da controllare in {args.out / 'REVISIONE.md'}")


if __name__ == "__main__":
    main()