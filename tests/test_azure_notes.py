"""Test di azure_notes con client finti: nessun emulatore e nessuna rete."""
import pytest

from nihongo_agent.azure_notes import (CosmosNotesIndex, compare_hits, download_notes,
                                       to_items, sync_notes, vector_policies)
from nihongo_agent.notes import load_chunks


class FakeContainer:
    """Un container Blob in memoria: nomi -> byte."""
    def __init__(self, files=None):
        self.files = dict(files or {})

    def upload_blob(self, name, data, overwrite=False):
        self.files[name] = data

    def list_blobs(self):
        return [type("B", (), {"name": n})() for n in self.files]

    def delete_blob(self, name):
        del self.files[name]

    def download_blob(self, name):
        data = self.files[name]
        return type("D", (), {"readall": lambda self: data})()


def test_sync_then_download_roundtrip(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "lez").mkdir(parents=True)
    (src / "lez" / "1.md").write_text("# Particelle\n\nwa e ga", encoding="utf-8")
    (src / "foto.png").write_bytes(b"\x89PNG")
    container = FakeContainer({"vecchio.md": b"cancellato da me"})
    assert sync_notes(container, src) == (1, 1)
    assert list(container.files) == ["lez/1.md"]
    assert download_notes(container, dst) == 1
    assert load_chunks(dst)[0]["source"] == "1.md › Particelle"


def test_vector_policies_match_each_other():
    embedding, indexing = vector_policies(dim=4)
    vec = embedding["vectorEmbeddings"][0]
    assert vec["dimensions"] == 4 and vec["distanceFunction"] == "cosine"
    assert indexing["vectorIndexes"][0]["path"] == vec["path"]
    assert {"path": vec["path"] + "/*"} in indexing["excludedPaths"]


def test_to_items_checks_lengths_and_ids():
    items = to_items([{"source": "a.md › x", "text": "uno"}], [[0.1, 0.2]])
    assert items == [{"id": "chunk-0000", "source": "a.md › x", "text": "uno", "embedding": [0.1, 0.2]}]
    with pytest.raises(ValueError):
        to_items([{"source": "a", "text": "b"}], [])


class FakeCosmos:
    def __init__(self, rows):
        self.rows, self.calls = rows, []

    def query_items(self, **kwargs):
        self.calls.append(kwargs)
        return iter(self.rows)


def test_search_has_notes_index_shape_and_sorts_by_similarity():
    rows = [{"source": "s", "text": "b", "score": 0.61}, {"source": "s", "text": "a", "score": 0.8}]
    fake = FakeCosmos(rows)
    tasks = []

    def embed(texts, task):
        tasks.append(task)
        return [[0.0, 1.0]]

    hits = CosmosNotesIndex(fake, embed).search("domanda", k=2)
    assert [h["text"] for h in hits] == ["a", "b"]
    assert hits[0] == {"source": "s", "text": "a", "score": 0.8}
    assert tasks == ["RETRIEVAL_QUERY"]
    call = fake.calls[0]
    assert "TOP 2" in call["query"] and call["parameters"][0]["value"] == [0.0, 1.0]
    assert call["enable_cross_partition_query"] is True


def test_compare_hits():
    a = [{"source": "s", "text": "1", "score": 0.80}, {"source": "s", "text": "2", "score": 0.70}]
    b = [{"source": "s", "text": "2", "score": 0.71}, {"source": "s", "text": "1", "score": 0.80}]
    assert compare_hits(a, b) == {"same_set": True, "same_order": False, "overlap": 2,
                                  "max_score_diff": 0.01}