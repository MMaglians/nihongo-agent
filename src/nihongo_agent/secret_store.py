"""Da dove arrivano i segreti. Qui: variabili d'ambiente. Nel cloud: Azure Key Vault.

Il resto del codice chiama solo get_secret("NOME") e non sa da dove arriva il valore.
Si sceglie con SECRETS_BACKEND=env (default) oppure SECRETS_BACKEND=keyvault.
"""
import os


class EnvSecrets:
    """Segreti dalle variabili d'ambiente (in locale le carica il .env, in Docker il compose)."""
    name = "variabili d'ambiente"

    def get(self, key: str) -> str | None:
        return os.getenv(key)


class KeyVaultSecrets:
    """Segreti da Azure Key Vault, con l'identità di DefaultAzureCredential.

    Non usato in locale (serve una subscription). Per attivarlo:
    uv add azure-identity azure-keyvault-secrets, poi SECRETS_BACKEND=keyvault e AZURE_KEY_VAULT_URL.
    """
    name = "Azure Key Vault"

    def __init__(self, vault_url: str | None = None, client=None):
        if client is None:
            from azure.identity import DefaultAzureCredential
            from azure.keyvault.secrets import SecretClient
            client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())
        self.client = client

    @staticmethod
    def vault_name(key: str) -> str:
        """Key Vault accetta solo lettere, cifre e trattini: GEMINI_API_KEY -> gemini-api-key."""
        return key.lower().replace("_", "-")

    def get(self, key: str) -> str | None:
        from azure.core.exceptions import ResourceNotFoundError
        try:
            return self.client.get_secret(self.vault_name(key)).value
        except ResourceNotFoundError:
            return None


def provider_from_env():
    backend = os.getenv("SECRETS_BACKEND", "env").strip().lower()
    if backend == "env":
        return EnvSecrets()
    if backend == "keyvault":
        url = os.getenv("AZURE_KEY_VAULT_URL")
        if not url:
            raise RuntimeError("SECRETS_BACKEND=keyvault ma AZURE_KEY_VAULT_URL è mancante")
        return KeyVaultSecrets(url)
    raise ValueError(f"SECRETS_BACKEND={backend!r} non valido: usa 'env' oppure 'keyvault'")


def get_secret(key: str, provider=None) -> str:
    """Il valore del segreto. Non lo stampa mai: in caso di errore dice solo il nome e la fonte."""
    provider = provider or provider_from_env()
    value = provider.get(key)
    if not value:
        raise RuntimeError(f"{key} mancante (fonte dei segreti: {provider.name}): "
                           "controlla il file .env o le variabili d'ambiente")
    return value