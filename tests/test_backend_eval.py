"""Test del confronto tra backend: run finto, nessuna rete."""
from nihongo_agent.backend_eval import compare_backends, run_interleaved

QUESTIONS = [{"category": "appunti", "expected_tool": "none", "question": f"q{i}"} for i in range(3)]


def fake_row(question, route_ok=True, answer_ok=True, sources=("a.md › x",)):
    return {**question, "answer": "...", "route": "recupera" if route_ok else "usa_tool",
            "tools_called": [], "observations": [], "retrieved": {"sources": list(sources)} if route_ok else None,
            "calls": 2, "input_tokens": 1000, "output_tokens": 100, "thinking_tokens": 0, "seconds": 3.0,
            "hit_limit": False, "api_error": False, "expected_route": "recupera", "tool_ok": True,
            "route_ok": route_ok, "answer_ok": answer_ok}


def test_interleaved_runs_each_question_once_per_backend_and_shuffles():
    calls = []

    def run_one(question, index):
        calls.append((question["question"], index))
        return fake_row(question)

    rows = run_interleaved(QUESTIONS, {"local": "L", "cosmos": "C"}, run_one)
    assert calls == [("q0", "L"), ("q0", "C"), ("q1", "L"), ("q1", "C"), ("q2", "L"), ("q2", "C")]
    assert sorted((r["question"], r["backend"]) for r in rows) == sorted(
        (q, b) for q in ["q0", "q1", "q2"] for b in ["local", "cosmos"])
    assert [r["backend"] for r in rows] != ["local", "cosmos"] * 3   # mescolate (seme fisso)


def test_compare_backends_pairs_by_question():
    rows = ([{**fake_row(q), "backend": "local"} for q in QUESTIONS]
            + [{**fake_row(QUESTIONS[0]), "backend": "cosmos"},
               {**fake_row(QUESTIONS[1], answer_ok=False), "backend": "cosmos"},
               {**fake_row(QUESTIONS[2], sources=("b.md › y",)), "backend": "cosmos"}])
    c = compare_backends(rows)
    assert c["summary"]["local"]["answer_ok"] == 3 and c["summary"]["cosmos"]["answer_ok"] == 2
    assert c["answer"] == {"n": 3, "v1_better": 0, "v1_worse": 1, "same": 2, "p_value": 1.0}
    assert c["retrieval_pairs"] == 3 and c["same_sources"] == 2