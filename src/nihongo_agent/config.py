"""Configurazione: legge la chiave e il nome del modello dal file .env."""
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gemini-3.5-flash-lite"

def get_model_name() -> str:
    """Nome del modello: GEMINI_MODEL nel .env, altrimenti il default."""
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

def get_api_key() -> str:
    """Restituisce la chiave senza mai stamparla."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY mancante: controlla il file .env")
    return key