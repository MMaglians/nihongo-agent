"""Test della scelta del backend degli appunti e dell'attesa dell'emulatore. Nessuna rete."""
import pytest

from nihongo_agent.azure_config import wait_until_ready
from nihongo_agent.azure_notes import CosmosNotesIndex
from nihongo_agent.notes import NotesIndex
from nihongo_agent.notes_backend import make_notes_index


def fake_embed(texts, task):
    return [[float(len(t)), 1.0] for t in texts]


class FakeCosmosContainer:
    def __init__(self, count=None):
        self.count = count

    def query_items(self, query, enable_cross_partition_query=False):
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        if self.count is None:
            raise CosmosResourceNotFoundError(message="missing", status_code=404)
        return iter([self.count])


def test_cosmos_backend_returns_cosmos_index():
    index, description = make_notes_index(fake_embed, "m", backend="cosmos",
                                          container=FakeCosmosContainer(9))
    assert isinstance(index, CosmosNotesIndex)
    assert description == "Cosmos DB, 9 pezzi"


@pytest.mark.parametrize("count, message", [(0, "vuoto"), (None, "inesistente")])
def test_cosmos_backend_explains_what_to_run(count, message):
    with pytest.raises(RuntimeError, match=message) as error:
        make_notes_index(fake_embed, "m", backend="cosmos", container=FakeCosmosContainer(count))
    assert "index_notes_cosmos.py" in str(error.value)


def test_local_backend_is_default(monkeypatch, tmp_path):
    monkeypatch.delenv("NOTES_BACKEND", raising=False)
    (tmp_path / "a.md").write_text("# Titolo\n\ntesto", encoding="utf-8")
    original = NotesIndex.load_or_build.__func__
    monkeypatch.setattr(NotesIndex, "load_or_build", classmethod(
        lambda cls, embed, model: original(cls, embed, model, folder=tmp_path,
                                           path=tmp_path / "idx.json")))
    index, description = make_notes_index(fake_embed, "m")
    assert isinstance(index, NotesIndex)
    assert description.startswith("locale, 1 pezzi")


def test_unknown_backend():
    with pytest.raises(ValueError, match="non valido"):
        make_notes_index(fake_embed, "m", backend="faiss")


class Response:
    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_wait_until_ready_retries_then_succeeds():
    answers = [ConnectionRefusedError(), Response(503), Response(200)]

    def opener(url, timeout):
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    slept = []
    assert wait_until_ready("http://x/ready", interval=2, opener=opener, sleep=slept.append) == 4
    assert slept == [2, 2]


def test_wait_until_ready_times_out_and_skips_without_url():
    def opener(url, timeout):
        raise ConnectionRefusedError()

    with pytest.raises(TimeoutError, match="non è pronto"):
        wait_until_ready("http://x/ready", timeout=4, interval=2, opener=opener, sleep=lambda s: None)
    assert wait_until_ready(None) == 0.0