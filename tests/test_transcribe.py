"""Test della trascrizione con un client finto e un PDF generato al volo: nessuna rete."""
import io
import json

from google.genai import errors, types
from pypdf import PdfReader, PdfWriter

from nihongo_agent.transcribe import page_blocks, transcribe_pdf


def make_pdf(path, pages):
    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(width=200, height=200)
    with open(path, "wb") as f:
        writer.write(f)


def answer(markdown, doubts=()):
    text = json.dumps({"markdown": markdown, "doubts": list(doubts)})
    content = types.Content(role="model", parts=[types.Part(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


class FakeModels:
    def __init__(self, responses):
        self.responses, self.pages_sent = list(responses), []

    def generate_content(self, model, contents, config):
        pdf_part = contents[0]
        self.pages_sent.append(len(PdfReader(io.BytesIO(pdf_part.inline_data.data)).pages))
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def test_page_blocks():
    assert page_blocks(12, 5) == [(1, 5), (6, 10), (11, 12)]


def test_blocks_are_written_with_doubts_and_review_list(tmp_path):
    pdf, out = tmp_path / "quaderno.pdf", tmp_path / "notes_draft"
    make_pdf(pdf, 7)
    client = FakeClient([
        answer("# Lezione 1\n\nwatashi wa gakusei desu", [{"page": 2, "text": "watashi gakusei", "issue": "manca 'wa'"}]),
        answer("# Lezione 2\n\nkore wa hon desu"),
    ])
    written = transcribe_pdf(client, "m", pdf, out, sleep=lambda s: None, log=lambda *a: None)
    assert [p.name for p in written] == ["quaderno_p001-005.md", "quaderno_p006-007.md"]
    assert client.models.pages_sent == [5, 2]
    review = (out / "REVISIONE.md").read_text(encoding="utf-8")
    assert "- [ ] p. 2: \"watashi gakusei\" — manca 'wa'" in review
    assert "nessun dubbio segnalato" in review


def test_rerun_skips_finished_blocks(tmp_path):
    pdf, out = tmp_path / "q.pdf", tmp_path / "notes_draft"
    make_pdf(pdf, 6)
    transcribe_pdf(FakeClient([answer("a"), answer("b")]), "m", pdf, out,
                   sleep=lambda s: None, log=lambda *a: None)
    client = FakeClient([])  # nessuna risposta disponibile: se chiamasse il modello, fallirebbe
    assert transcribe_pdf(client, "m", pdf, out, sleep=lambda s: None, log=lambda *a: None) == []


def test_page_range_and_quota_retry(tmp_path):
    pdf, out = tmp_path / "q.pdf", tmp_path / "notes_draft"
    make_pdf(pdf, 20)
    quota = errors.ClientError(429, {"error": {"message": "quota", "status": "RESOURCE_EXHAUSTED"}})
    waits = []
    client = FakeClient([quota, answer("x")])
    written = transcribe_pdf(client, "m", pdf, out, first_page=11, last_page=13,
                             sleep=waits.append, log=lambda *a: None)
    assert [p.name for p in written] == ["q_p011-013.md"]
    assert 60 in waits and client.models.pages_sent == [3, 3]