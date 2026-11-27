"""Test del gestore dei segreti: variabili d'ambiente e Key Vault finto. Nessuna rete."""
import pytest

from nihongo_agent.secret_store import EnvSecrets, KeyVaultSecrets, get_secret, provider_from_env


def test_env_secret_is_read(monkeypatch):
    monkeypatch.setenv("PROVA_KEY", "abc")
    assert get_secret("PROVA_KEY", EnvSecrets()) == "abc"


def test_missing_secret_names_key_and_source(monkeypatch):
    monkeypatch.delenv("PROVA_KEY", raising=False)
    with pytest.raises(RuntimeError, match="PROVA_KEY mancante.*variabili d'ambiente"):
        get_secret("PROVA_KEY", EnvSecrets())


class FakeVault:
    def __init__(self, secrets):
        self.secrets, self.asked = secrets, []

    def get_secret(self, name):
        from azure.core.exceptions import ResourceNotFoundError
        self.asked.append(name)
        if name not in self.secrets:
            raise ResourceNotFoundError("not found")
        return type("Secret", (), {"value": self.secrets[name]})()


def test_keyvault_maps_names_and_reads():
    vault = FakeVault({"gemini-api-key": "segreto"})
    provider = KeyVaultSecrets(client=vault)
    assert get_secret("GEMINI_API_KEY", provider) == "segreto"
    assert vault.asked == ["gemini-api-key"]


def test_keyvault_missing_secret_is_clear_error():
    with pytest.raises(RuntimeError, match="COSMOS_KEY mancante.*Key Vault"):
        get_secret("COSMOS_KEY", KeyVaultSecrets(client=FakeVault({})))


def test_backend_choice(monkeypatch):
    monkeypatch.delenv("SECRETS_BACKEND", raising=False)
    assert isinstance(provider_from_env(), EnvSecrets)
    monkeypatch.setenv("SECRETS_BACKEND", "keyvault")
    monkeypatch.delenv("AZURE_KEY_VAULT_URL", raising=False)
    with pytest.raises(RuntimeError, match="AZURE_KEY_VAULT_URL"):
        provider_from_env()
    monkeypatch.setenv("SECRETS_BACKEND", "boh")
    with pytest.raises(ValueError):
        provider_from_env()