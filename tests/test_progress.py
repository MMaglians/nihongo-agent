from nihongo_agent.progress import ProgressStore
from nihongo_agent.tools import get_dictionary
from nihongo_agent.tools_v1 import check_answer, make_quiz_v1, show_progress


def question(word="猫", correct="B"):
    return {"word": word, "reading": "ねこ", "correct": correct,
            "options": {"A": "dog", "B": "cat", "C": "water", "D": "to eat"}}


def test_check_records_and_clears_pending():
    store = ProgressStore(":memory:")
    store.add_pending([question()])
    result = store.check("猫", " b ")
    assert result["correct"] is True and result["meaning"] == "cat"
    assert "error" in store.check("猫", "B")  # già corretta: non più in sospeso


def test_unknown_word_is_an_error_not_a_crash():
    assert "error" in ProgressStore(":memory:").check("犬", "A")


def test_to_review_lists_words_wrong_more_often_than_right():
    store = ProgressStore(":memory:")
    for letter in ["A", "A", "B"]:          # 猫: 2 sbagliate, 1 giusta
        store.add_pending([question("猫")])
        store.check("猫", letter)
    store.add_pending([question("水")])
    store.check("水", "B")                   # 水: 1 giusta
    assert store.to_review() == ["猫"]
    assert store.summary() == {"answers": 4, "correct": 2, "accuracy": 0.5, "to_review": ["猫"]}


def test_progress_survives_a_new_session(tmp_path):
    path = tmp_path / "progress.db"
    store = ProgressStore(path)
    store.add_pending([question()])
    store.check("猫", "A")
    store.db.close()
    assert ProgressStore(path).to_review() == ["猫"]  # nuova "sessione", stesso file


def test_quiz_tool_flow_with_review():
    quiz = make_quiz_v1(n=1)
    q = quiz["questions"][0]
    wrong = next(letter for letter in "ABCD" if letter != q["correct"])
    assert check_answer(q["word"], wrong)["correct"] is False
    assert show_progress()["to_review"] == [q["word"]]
    review = make_quiz_v1(n=1, review=True)
    assert review["review"] is True and review["questions"][0]["word"] == q["word"]


def test_dictionary_quiz_ignores_unknown_review_words():
    questions = get_dictionary().quiz(2, words=["parola_inesistente"])
    assert len(questions) == 2  # torna al pool normale