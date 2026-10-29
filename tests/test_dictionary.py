import pytest

from nihongo_agent.dictionary import Dictionary
from nihongo_agent.tools import execute_tool, make_quiz
from conftest import SAMPLE


def test_lookup_shows_readable_pos_and_forms():
    entry = Dictionary(SAMPLE).lookup("食べる")[0]
    assert entry["senses"][0]["pos"] == ["Ichidan verb", "transitive verb"]
    assert entry["kanji"] == ["食べる"] and entry["readings"] == ["たべる"]


def test_kana_only_word_is_found():
    entry = Dictionary(SAMPLE).lookup("ありがとう")[0]
    assert entry["kanji"] == [] and entry["senses"][0]["meanings"] == ["thank you"]


def test_quiz_structure_and_correct_answer():
    questions = Dictionary(SAMPLE, seed=3).quiz(3)
    assert len(questions) == 3
    meanings = {"猫": "cat", "食べる": "to eat", "飲む": "to drink", "水": "water",
                "大きい": "big", "ありがとう": "thank you"}
    for q in questions:
        assert list(q["options"]) == ["A", "B", "C", "D"]
        assert len(set(q["options"].values())) == 4  # nessun duplicato
        assert q["options"][q["correct"]] == meanings[q["word"]]


def test_make_quiz_clamps_and_accepts_float():
    assert len(make_quiz(3.0)["questions"]) == 3
    assert len(make_quiz(500)["questions"]) == 6  # non più delle parole disponibili
    assert "error" in execute_tool("make_quiz", {"numero": 3})


def test_quiz_refuses_tiny_dictionary():
    tiny = {"words": SAMPLE["words"][:3]}
    with pytest.raises(ValueError):
        Dictionary(tiny).quiz(1)