"""Configurazione dei servizi Azure (emulatori in locale, cloud domani): tutto dal file .env."""
import os

from dotenv import load_dotenv

load_dotenv()

# Default = emulatori locali. Nel cloud cambiano solo i valori nel .env, non il codice.
DEFAULTS = {
    "AZURE_STORAGE_CONNECTION_STRING": "UseDevelopmentStorage=true",  # Azurite
    "AZURE_NOTES_CONTAINER": "notes",
    "COSMOS_ENDPOINT": "http://localhost:8081",                        # Cosmos DB emulator
    "COSMOS_DATABASE": "nihongo",
    "COSMOS_CONTAINER": "notes",
}


def setting(name: str) -> str:
    """Un'impostazione: dal .env, altrimenti il default. Errore chiaro se manca del tutto."""
    value = os.getenv(name, DEFAULTS.get(name))
    if not value:
        raise RuntimeError(f"{name} mancante: controlla il file .env")
    return value