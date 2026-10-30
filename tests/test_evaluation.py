import pytest
from google.genai import errors, types

from nihongo_agent.evaluation import (by_category, evaluate, read_questions, run_question, summarize,
                                      tool_ok, wilson_interval)
from test_agent import FakeClient, call_response, text_response


def with_usage(response, inp, out, think=0):
    response.usage_metadata = types.GenerateContentResponseUsageMetadata(
        prompt_token_count=inp, candidates_token_count=out, thoughts_token_count=think)
    return response


def test_wilson_matches_known_values():
    lo, hi = wilson_interval(18, 20)
    assert (round(lo, 2), round(hi, 2)) == (0.70, 0.97)
    lo, hi = wilson_interval(20, 20)
    assert round(lo, 2) == 0.84 and hi == 1.0
    assert wilson_interval(0, 0) == (0.0, 1.0)


def test_read_questions_skips_comments_and_rejects_bad_lines(tmp_path):
    f = tmp_path / "q.txt"
    f.write_text("# commento\n\nparola | lookup_word | Che cosa vuol dire 猫?\nsaluto | none | Ciao | come stai\n",
                 encoding="utf-8")
    qs = read_questions(f)
    assert qs[1] == {"category": "saluto", "expected_tool": "none", "question": "Ciao | come stai"}
    f.write_text("parola | strumento_strano | domanda\n", encoding="utf-8")
    with pytest.raises(ValueError):
        read_questions(f)


def test_tool_ok_rules():
    assert tool_ok("none", []) and not tool_ok("none", ["lookup_word"])
    assert tool_ok("lookup_word", ["lookup_word", "lookup_word"])
    assert not tool_ok("lookup_word", ["lookup_word", "make_quiz"]) and not tool_ok("lookup_word", [])


def test_run_question_collects_metrics():
    client = FakeClient(responses=[with_usage(call_response("lookup_word", {"word": "猫"}), 100, 10, 5),
                                   with_usage(text_response("gatto"), 150, 20, 0)])
    r = run_question(client, "m", "猫?")
    assert r["tools_called"] == ["lookup_word"] and r["steps"] == 2 and r["answer"] == "gatto"
    assert (r["input_tokens"], r["output_tokens"], r["thinking_tokens"]) == (250, 30, 5)
    assert '"found": true' in r["observations"][0] and not r["hit_limit"]


def test_evaluate_retries_once_after_api_error_and_marks_failures():
    err = errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}})

    class Flaky:
        def __init__(self): self.calls = 0
        def generate_content(self, model, contents, config):
            self.calls += 1
            if self.calls == 1:
                raise err
            return text_response("Ciao!")

    class C:
        models = Flaky()

    waits = []
    rows = evaluate(C(), "m", [{"category": "saluto", "expected_tool": "none", "question": "Ciao"}],
                    pause=0, sleep=waits.append, log=lambda *_: None)
    assert rows[0]["tool_ok"] and not rows[0]["api_error"] and 60 in waits

    class Dead:
        def generate_content(self, model, contents, config):
            raise err

    class D:
        models = Dead()

    rows = evaluate(D(), "m", [{"category": "saluto", "expected_tool": "none", "question": "Ciao"}],
                    pause=0, sleep=lambda s: None, log=lambda *_: None)
    assert rows[0]["api_error"] and rows[0]["tool_ok"] is False  # un errore API non conta come successo


def test_summarize_and_by_category():
    base = {"steps": 2, "seconds": 2.0, "input_tokens": 1000, "output_tokens": 50, "thinking_tokens": 50,
            "hit_limit": False, "api_error": False}
    rows = [{**base, "category": "a", "tool_ok": True, "answer_ok": True},
            {**base, "category": "a", "tool_ok": True, "answer_ok": False},
            {**base, "category": "b", "tool_ok": False, "answer_ok": None}]
    s = summarize(rows)
    assert s["tool_ok"] == 2 and s["labeled"] == 2 and s["answer_ok"] == 1
    assert s["mean_input_tokens"] == 1000 and s["mean_output_tokens"] == 100
    assert abs(s["cost_usd_total"] - (3000 * 0.30 + 300 * 2.50) / 1e6) < 1e-12
    assert by_category(rows)["a"] == {"n": 2, "tool_ok": 2, "labeled": 2, "answer_ok": 1}