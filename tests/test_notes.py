import json

from nihongo_agent.notes import NotesIndex, load_chunks


def write_notes(folder):
    folder.mkdir()
    (folder / "lezione1.md").write_text(
        "# Particelle\n\nは segna il tema della frase: わたしは がくせいです.\n\n"
        "# Verbi\n\n食べる significa mangiare, verbo ichidan.\n", encoding="utf-8")
    (folder / "ignorato.pdf").write_bytes(b"%PDF")


def test_chunks_follow_headings(tmp_path):
    write_notes(tmp_path / "notes")
    chunks = load_chunks(tmp_path / "notes")
    assert [c["source"] for c in chunks] == ["lezione1.md › Particelle", "lezione1.md › Verbi"]


def test_long_sections_are_split(tmp_path):
    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "a.txt").write_text("\n\n".join(["x" * 400] * 5), encoding="utf-8")
    chunks = load_chunks(folder, max_chars=1000)
    assert len(chunks) == 3 and all(len(c["text"]) <= 1000 for c in chunks)


def test_search_finds_the_right_section(tmp_path, fake_embed):
    write_notes(tmp_path / "notes")
    index = NotesIndex.build(load_chunks(tmp_path / "notes"), fake_embed)
    hits = index.search("a cosa serve は? わたしは", k=1)
    assert hits[0]["source"] == "lezione1.md › Particelle"


def test_cache_is_reused_until_notes_change(tmp_path, fake_embed):
    folder, path = tmp_path / "notes", tmp_path / "index.json"
    write_notes(folder)
    calls = []

    def counting_embed(texts, task):
        calls.append(task)
        return fake_embed(texts, task)

    _, rebuilt = NotesIndex.load_or_build(counting_embed, "m", folder, path)
    assert rebuilt and json.loads(path.read_text(encoding="utf-8"))["model"] == "m"
    _, rebuilt = NotesIndex.load_or_build(counting_embed, "m", folder, path)
    assert not rebuilt and calls == ["RETRIEVAL_DOCUMENT"]   # nessun nuovo embedding
    (folder / "lezione2.md").write_text("# Nuova\n\nnuovo appunto", encoding="utf-8")
    _, rebuilt = NotesIndex.load_or_build(counting_embed, "m", folder, path)
    assert rebuilt


def test_empty_folder_gives_no_hits(tmp_path, fake_embed):
    (tmp_path / "notes").mkdir()
    index = NotesIndex.build(load_chunks(tmp_path / "notes"), fake_embed)
    assert index.search("qualcosa") == []