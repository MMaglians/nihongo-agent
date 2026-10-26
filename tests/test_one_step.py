"""Test senza rete: un client finto che imita le risposte di Gemini."""
from google.genai import types

from nihongo_agent.one_step import ask_once
from nihongo_agent.tools import execute_tool, lookup_word


def _text_response(text: str) -> types.GenerateContentResponse:
    content = types.Content(role="model", parts=[types.Part(text=text)])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


def _call_response(name: str, args: dict) -> types.GenerateContentResponse:
    part = types.Part(function_call=types.FunctionCall(name=name, args=args))
    content = types.Content(role="model", parts=[part])
    return types.GenerateContentResponse(candidates=[types.Candidate(content=content)])


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.received = []  # salva ciò che riceve, per controllarlo

    def generate_content(self, model, contents, config):
        self.received.append(list(contents))
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.models = FakeModels(responses)


def test_lookup_word_found_and_missing():
    assert lookup_word("猫")["meaning"] == "cat"
    assert lookup_word("犬") == {"found": False, "word": "犬"}


def test_execute_tool_handles_bad_input():
    assert "error" in execute_tool("tool_inesistente", {})
    assert "error" in execute_tool("lookup_word", {"parola": "猫"})


def test_answer_without_tool():
    client = FakeClient([_text_response("Ciao!")])
    answer, trace = ask_once(client, "fake-model", "Ciao")
    assert answer == "Ciao!"
    assert trace == ["modello: risponde senza tool"]


def test_one_tool_round_trip():
    client = FakeClient([
        _call_response("lookup_word", {"word": "猫"}),
        _text_response("猫 (ねこ) significa gatto."),
    ])
    answer, trace = ask_once(client, "fake-model", "Che cosa vuol dire 猫?")
    assert "gatto" in answer
    assert trace[0] == "azione: lookup_word({'word': '猫'})"
    # La seconda chiamata deve contenere: domanda, turno del modello, risultato del tool.
    second_call = client.models.received[1]
    assert [c.role for c in second_call] == ["user", "model", "user"]
    fr = second_call[2].parts[0].function_response
    assert fr.name == "lookup_word" and fr.response["meaning"] == "cat"