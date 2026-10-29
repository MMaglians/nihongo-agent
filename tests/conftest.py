"""Fixture comuni: un mini dizionario nello stesso formato di JMdict (nessun file vero)."""
import pytest

from nihongo_agent import tools
from nihongo_agent.dictionary import Dictionary


def make_word(wid, kanji, kana, pos, glosses, common=True):
    return {
        "id": wid,
        "kanji": [{"common": common, "text": k, "tags": []} for k in kanji],
        "kana": [{"common": common, "text": k, "tags": [], "appliesToKanji": ["*"]} for k in kana],
        "sense": [{"partOfSpeech": pos, "gloss": [{"lang": "eng", "type": None, "text": g} for g in glosses]}],
    }


SAMPLE = {
    "version": "test",
    "dictDate": "2026-01-01",
    "tags": {"n": "noun (common) (futsuumeishi)", "v1": "Ichidan verb", "v5m": "Godan verb with 'mu' ending",
             "adj-i": "adjective (keiyoushi)", "vt": "transitive verb", "intj": "interjection (kandoushi)"},
    "words": [
        make_word("1", ["猫"], ["ねこ"], ["n"], ["cat", "feline"]),
        make_word("2", ["食べる"], ["たべる"], ["v1", "vt"], ["to eat"]),
        make_word("3", ["飲む"], ["のむ"], ["v5m"], ["to drink"]),
        make_word("4", ["水"], ["みず"], ["n"], ["water"]),
        make_word("5", ["大きい"], ["おおきい"], ["adj-i"], ["big", "large"]),
        make_word("6", [], ["ありがとう"], ["intj"], ["thank you"]),
    ],
}


@pytest.fixture(autouse=True)
def sample_dictionary():
    """Ogni test usa il mini dizionario, mai il file vero."""
    tools.set_dictionary(Dictionary(SAMPLE, seed=1))
    yield
    tools.set_dictionary(None)