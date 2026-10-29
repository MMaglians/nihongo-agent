import pytest
from google.genai import errors

from nihongo_agent.retry import generate_with_retry


class FlakyModels:
    """Fallisce con l'errore indicato per i primi `fails` tentativi."""
    def __init__(self, exc, fails):
        self.exc, self.fails, self.calls = exc, fails, 0

    def generate_content(self, model, contents, config):
        self.calls += 1
        if self.calls <= self.fails:
            raise self.exc
        return "ok"


class Client:
    def __init__(self, models):
        self.models = models


def server_error():
    return errors.ServerError(503, {"error": {"status": "UNAVAILABLE", "message": "overloaded"}})


def test_retries_then_succeeds():
    waits = []
    client = Client(FlakyModels(server_error(), fails=2))
    out = generate_with_retry(client, model="m", contents=[], config=None, sleep=waits.append)
    assert out == "ok" and client.models.calls == 3 and waits == [2.0, 4.0]


def test_gives_up_after_all_tries():
    client = Client(FlakyModels(server_error(), fails=99))
    with pytest.raises(errors.ServerError):
        generate_with_retry(client, model="m", contents=[], config=None, sleep=lambda s: None)
    assert client.models.calls == 4


def test_client_errors_are_not_retried():
    bad = errors.ClientError(429, {"error": {"status": "RESOURCE_EXHAUSTED", "message": "quota"}})
    client = Client(FlakyModels(bad, fails=99))
    with pytest.raises(errors.ClientError):
        generate_with_retry(client, model="m", contents=[], config=None, sleep=lambda s: None)
    assert client.models.calls == 1