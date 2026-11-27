"""Configurazione: legge la chiave e il nome del modello dal file .env."""
import os

from dotenv import load_dotenv

from nihongo_agent.secret_store import get_secret

load_dotenv()

DEFAULT_MODEL = "gemini-3.5-flash-lite"

def get_model_name() -> str:
    """Nome del modello: GEMINI_MODEL nel .env, altrimenti il default."""
    return os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

def get_api_key() -> str:
    """Restituisce la chiave senza mai stamparla (dal gestore dei segreti)."""
    return get_secret("GEMINI_API_KEY")


DEFAULT_EMBED_MODEL = "gemini-embedding-001"

def get_embed_model_name() -> str:
    """Modello di embedding: GEMINI_EMBED_MODEL nel .env, altrimenti il default."""
    return os.getenv("GEMINI_EMBED_MODEL", DEFAULT_EMBED_MODEL)



DEFAULT_JUDGE_MODEL = "gemma-4-31b-it"

def get_judge_model_name() -> str:
    """Modello del giudice: JUDGE_MODEL nel .env, altrimenti il default."""
    return os.getenv("JUDGE_MODEL", DEFAULT_JUDGE_MODEL)