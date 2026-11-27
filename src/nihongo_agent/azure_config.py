"""Configurazione dei servizi Azure (emulatori in locale, cloud poi): tutto dal file .env."""
import os
import time
import urllib.request

from dotenv import load_dotenv

from nihongo_agent.secret_store import get_secret

load_dotenv()

# Default = emulatori locali. Nel cloud cambiano solo i valori nel .env, non il codice.
DEFAULTS = {
    "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",  # Azurite
    "AZURE_NOTES_CONTAINER": "notes",
    "COSMOS_ENDPOINT": "http://localhost:8081",                        # Cosmos DB emulator
    "COSMOS_DATABASE": "nihongo",
    "COSMOS_CONTAINER": "notes",
    # false: l'SDK usa sempre COSMOS_ENDPOINT e non l'indirizzo che l'emulatore "annuncia"
    # (localhost), che dentro Docker Compose sarebbe sbagliato. true solo con account multi-regione.
    "COSMOS_ENDPOINT_DISCOVERY": "false",
}


def setting(name: str) -> str:
    """Un'impostazione: dal .env, altrimenti il default. Errore chiaro se manca del tutto."""
    value = os.getenv(name, DEFAULTS.get(name))
    if not value:
        raise RuntimeError(f"{name} mancante: controlla il file .env")
    return value


def wait_until_ready(url: str | None, timeout: float = 180, interval: float = 3,
                     opener=None, sleep=time.sleep) -> float:
    """Aspetta che `url` risponda 200 (es. /ready dell'emulatore). Ritorna i secondi attesi.

    url vuoto = nessuna attesa (nel cloud il servizio è già acceso).
    """
    if not url:
        return 0.0
    if opener is None:   # niente proxy: è un servizio sulla rete locale o di Docker
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({})).open
    waited = 0.0
    while True:
        try:
            with opener(url, timeout=5) as response:
                if response.status == 200:
                    return waited
        except OSError:          # connessione rifiutata, nome non ancora risolto, timeout...
            pass
        if waited >= timeout:
            raise TimeoutError(f"{url} non è pronto dopo {timeout:.0f} s: il container è avviato?")
        sleep(interval)
        waited += interval


def cosmos_client():
    """Client Cosmos: endpoint dalle impostazioni, chiave dal gestore dei segreti."""
    from azure.cosmos import CosmosClient
    waited = wait_until_ready(os.getenv("COSMOS_READY_URL"))
    if waited:
        print(f"Cosmos DB pronto dopo {waited:.0f} s.")
    discovery = setting("COSMOS_ENDPOINT_DISCOVERY").lower() == "true"
    return CosmosClient(setting("COSMOS_ENDPOINT"), credential=get_secret("COSMOS_KEY"),
                        enable_endpoint_discovery=discovery)


def notes_container(client=None):
    """Il container Cosmos con i vettori degli appunti (deve già esistere)."""
    client = client or cosmos_client()
    return client.get_database_client(setting("COSMOS_DATABASE")).get_container_client(
        setting("COSMOS_CONTAINER"))