"""Test del grafo v1 con un client finto: nessuna chiamata di rete."""
import json

from google.genai import types
from langgraph.checkpoint.memory import InMemorySaver

from nihongo_agent.graph import build_graph, run_turn_v1
from nihongo_agent.tracing import TraceLog


def text_response(text):
    content = types.Content(role="model", parts=[types.Part(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def call_response(name, args):
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def route_response(route):
    return text_response(json.dumps({"route": route}))


class FakeModels:
    """Restituisce le risposte in ordine; finita la lista, ripete `always`."""

    def __init__(self, responses=None, always=None):
        self.responses, self.always = list(responses or []), always
        self.calls, self.seen = 0, []

    def generate_content(self, model, contents, config):
        self.calls += 1
        self.seen.append((contents, config))
        return self.responses.pop(0) if self.responses else self.always


class FakeClient:
    def __init__(self, **kw):
        self.models = FakeModels(**kw)


def make(client, **kw):
    return build_graph(client, "m", checkpointer=InMemorySaver(), **kw)


def roles(graph, thread="t1"):
    return [m["role"] for m in graph.get_state({"configurable": {"thread_id": thread}}).values["messages"]]


def test_rispondi_goes_without_tools():
    client = FakeClient(responses=[route_response("rispondi"), text_response("Ciao!")])
    graph = make(client)
    assert run_turn_v1(graph, "t1", "Ciao") == "Ciao!"
    assert roles(graph) == ["user", "model"]
    _, config = client.models.seen[1]
    assert config.tools is None  # nel ramo "rispondi" il modello non vede i tool


def test_usa_tool_then_answer():
    client = FakeClient(responses=[route_response("usa_tool"),
                                   call_response("lookup_word", {"word": "猫"}), text_response("gatto")])
    graph = make(client)
    assert run_turn_v1(graph, "t1", "猫?") == "gatto"
    assert roles(graph) == ["user", "model", "user", "model"]
    messages = graph.get_state({"configurable": {"thread_id": "t1"}}).values["messages"]
    assert messages[2]["parts"][0]["function_response"]["response"]["found"] is True


def test_step_limit_stops_a_runaway_agent():
    client = FakeClient(responses=[route_response("usa_tool")],
                        always=call_response("lookup_word", {"word": "猫"}))
    graph = make(client, max_steps=3)
    answer = run_turn_v1(graph, "t1", "x")
    assert "limite di 3 passi" in answer
    assert client.models.calls == 1 + 3  # router + 3 passi
    assert roles(graph)[-1] == "model"   # ruoli ancora alternati


def test_memory_per_thread():
    client = FakeClient(responses=[route_response("rispondi"), text_response("uno"),
                                   route_response("rispondi"), text_response("due"),
                                   route_response("rispondi"), text_response("tre")])
    graph = make(client)
    run_turn_v1(graph, "a", "primo")
    run_turn_v1(graph, "a", "secondo")
    run_turn_v1(graph, "b", "nuovo")
    assert roles(graph, "a") == ["user", "model", "user", "model"]
    assert roles(graph, "b") == ["user", "model"]
    contents, _ = client.models.seen[3]  # seconda risposta del thread "a"
    assert len(contents) == 3            # il modello ha visto anche il turno precedente


def test_context_is_sent_but_not_stored():
    client = FakeClient(responses=[route_response("recupera"), text_response("ok")])
    graph = make(client)
    run_turn_v1(graph, "t1", "cosa dicono i miei appunti sulla particella は?")
    contents, _ = client.models.seen[1]
    assert any("Contesto dagli appunti" in (p.text or "") for c in contents for p in c.parts)
    assert roles(graph) == ["user", "model"]  # in memoria solo domanda e risposta


def test_invalid_router_output_falls_back_to_tools():
    trace = TraceLog()
    client = FakeClient(responses=[text_response("non è JSON"), text_response("risposta")])
    graph = build_graph(client, "m", trace=trace, checkpointer=InMemorySaver())
    run_turn_v1(graph, "t1", "x")
    route = [e for e in trace.events if e["kind"] == "route"][0]["route"]
    assert route == "usa_tool"
    assert any(e["kind"] == "error" for e in trace.events)


def test_empty_response_is_handled():
    client = FakeClient(responses=[route_response("usa_tool"), types.GenerateContentResponse(candidates=[])])
    graph = make(client)
    assert "non ha prodotto" in run_turn_v1(graph, "t1", "x")
    assert roles(graph) == ["user", "model"]


def test_trace_has_the_same_events_as_v0_plus_route(tmp_path):
    path = tmp_path / "logs" / "t.jsonl"
    client = FakeClient(responses=[route_response("usa_tool"),
                                   call_response("lookup_word", {"word": "猫"}), text_response("gatto")])
    graph = build_graph(client, "m", trace=TraceLog(path), checkpointer=InMemorySaver())
    run_turn_v1(graph, "t1", "猫?")
    kinds = [json.loads(line)["kind"] for line in path.read_text(encoding="utf-8").splitlines()]
    assert kinds == ["user", "model", "route", "model", "tool", "model", "final"]