import json

from google.genai import types

from nihongo_agent.agent import run_turn
from nihongo_agent.tracing import TraceLog


def text_response(text):
    content = types.Content(role="model", parts=[types.Part(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def call_response(name, args):
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


class FakeModels:
    def __init__(self, responses=None, always=None):
        self.responses, self.always, self.calls = list(responses or []), always, 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        return self.always if self.always is not None else self.responses.pop(0)


class FakeClient:
    def __init__(self, **kw):
        self.models = FakeModels(**kw)


def roles(history):
    return [c.role for c in history]


def test_no_tool_one_step():
    client, history = FakeClient(responses=[text_response("Ciao!")]), []
    assert run_turn(client, "m", history, "Ciao") == "Ciao!"
    assert roles(history) == ["user", "model"] and client.models.calls == 1


def test_tool_then_answer():
    client = FakeClient(responses=[call_response("lookup_word", {"word": "猫"}), text_response("gatto")])
    history = []
    assert run_turn(client, "m", history, "猫?") == "gatto"
    assert roles(history) == ["user", "model", "user", "model"]
    assert history[2].parts[0].function_response.response["found"] is True


def test_two_tools_in_a_row_before_answer():
    client = FakeClient(responses=[call_response("lookup_word", {"word": "猫"}),
                                   call_response("make_quiz", {"n": 2}), text_response("fatto")])
    history = []
    assert run_turn(client, "m", history, "x") == "fatto" and client.models.calls == 3
    assert roles(history) == ["user", "model", "user", "model", "user", "model"]


def test_step_limit_stops_a_runaway_agent():
    client, history = FakeClient(always=call_response("lookup_word", {"word": "猫"})), []
    answer = run_turn(client, "m", history, "x", max_steps=3)
    assert "limite di 3 passi" in answer and client.models.calls == 3
    assert roles(history)[-1] == "model"  # ruoli ancora alternati


def test_history_survives_across_turns():
    client = FakeClient(responses=[text_response("uno"), text_response("due")])
    history = []
    run_turn(client, "m", history, "a")
    run_turn(client, "m", history, "b")
    assert roles(history) == ["user", "model", "user", "model"]


def test_empty_response_is_handled():
    client, history = FakeClient(responses=[types.GenerateContentResponse(candidates=[])]), []
    assert "non ha prodotto" in run_turn(client, "m", history, "x")
    assert roles(history) == ["user", "model"]


def test_trace_file_records_the_steps(tmp_path):
    path = tmp_path / "logs" / "t.jsonl"
    client = FakeClient(responses=[call_response("lookup_word", {"word": "猫"}), text_response("gatto")])
    run_turn(client, "m", [], "猫?", trace=TraceLog(path))
    kinds = [json.loads(line)["kind"] for line in path.read_text(encoding="utf-8").splitlines()]
    assert kinds == ["user", "model", "tool", "model", "final"]