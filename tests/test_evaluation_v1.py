"""Test della valutazione v1 con client finto: nessuna rete."""
import json

from google.genai import types

from nihongo_agent.evaluation_v1 import evaluate_v1, paired, redact, sign_test, summarize_v1


def text_response(text):
    content = types.Content(role="model", parts=[types.Part(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def call_response(name, args):
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def route(r):
    return text_response(json.dumps({"route": r}))


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)

    def generate_content(self, model, contents, config):
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


QUESTIONS = [
    {"category": "parola", "expected_tool": "lookup_word", "question": "猫?"},
    {"category": "senza_tool", "expected_tool": "none", "question": "Ciao"},
]


def run(responses):
    return evaluate_v1(FakeClient(responses), "m", QUESTIONS, sleep=lambda s: None, log=lambda *a: None)


def test_evaluate_measures_route_tools_and_calls():
    rows = run([route("usa_tool"), call_response("lookup_word", {"word": "猫"}), text_response("gatto"),
                route("rispondi"), text_response("Ciao!")])
    assert [r["route_ok"] for r in rows] == [True, True]
    assert [r["tool_ok"] for r in rows] == [True, True]
    assert [r["calls"] for r in rows] == [3, 2]  # il router conta come chiamata


def test_wrong_route_is_detected():
    rows = run([route("rispondi"), text_response("non posso verificare"),
                route("usa_tool"), text_response("Ciao!")])
    assert rows[0]["route_ok"] is False and rows[0]["tool_ok"] is False
    assert rows[1]["route_ok"] is False and rows[1]["tool_ok"] is True


def test_sign_test():
    assert sign_test(0, 0) == 1.0
    assert sign_test(5, 0) == 0.0625          # 2 * (1/2)^5
    assert round(sign_test(3, 1), 3) == 0.625


def test_paired_comparison():
    v0 = [{"question": "a", "tool_ok": False}, {"question": "b", "tool_ok": True}, {"question": "c", "tool_ok": True}]
    v1 = [{"question": "a", "tool_ok": True}, {"question": "b", "tool_ok": True},
          {"question": "c", "tool_ok": False}, {"question": "nuova", "tool_ok": True}]
    assert paired(v0, v1, "tool_ok") == {"n": 3, "v1_better": 1, "v1_worse": 1, "same": 1, "p_value": 1.0}


def test_redact_removes_private_text_only():
    data = {"model": "m", "rows": [
        {"category": "appunti", "answer": "segreto", "retrieved": {"sources": ["q.md › x"], "scores": [0.8]}},
        {"category": "parola", "answer": "gatto", "retrieved": None}]}
    public = redact(data)
    assert public["rows"][0]["answer"].startswith("[omessa")
    assert public["rows"][0]["retrieved"] == {"scores": [0.8]}
    assert public["rows"][1]["answer"] == "gatto"
    assert data["rows"][0]["answer"] == "segreto"  # l'originale non viene toccato


def test_summary_counts_and_cost():
    rows = run([route("usa_tool"), call_response("lookup_word", {"word": "猫"}), text_response("gatto"),
                route("rispondi"), text_response("Ciao!")])
    rows[0]["answer_ok"], rows[1]["answer_ok"] = True, False
    s = summarize_v1(rows)
    assert (s["route_ok"], s["tool_ok"], s["answer_ok"], s["labeled"]) == (2, 2, 1, 2)
    assert s["mean_calls"] == 2.5 and s["cost_usd_per_question"] == 0.0  # client finto: zero token