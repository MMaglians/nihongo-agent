"""Chat a riga di comando con l'agente. Scrivi 'esci' per uscire."""
from pathlib import Path

from google import genai
from google.genai import errors

from nihongo_agent.agent import run_turn
from nihongo_agent.config import get_api_key, get_model_name
from nihongo_agent.tools import get_dictionary
from nihongo_agent.tracing import TraceLog

LOG_PATH = Path(__file__).resolve().parent / "logs" / "traces.jsonl"


def main() -> None:
    get_dictionary()  # se il file manca, l'errore arriva subito e chiaro
    client = genai.Client(api_key=get_api_key())
    model = get_model_name()
    trace = TraceLog(LOG_PATH, echo=True)
    history: list = []
    print(f"Agente pronto ({model}). Tracce in {LOG_PATH}. Scrivi 'esci' per uscire.")
    while True:
        try:
            text = input("\nTu> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"esci", "exit", "quit"}:
            break
        if not text:
            continue
        size = len(history)
        try:
            print("\nAgente>", run_turn(client, model, history, text, trace=trace))
        except errors.APIError as exc:
            del history[size:]  # scarta il turno rotto: la conversazione resta valida
            print(f"[errore API {exc.code}] {exc.message}")


if __name__ == "__main__":
    main()