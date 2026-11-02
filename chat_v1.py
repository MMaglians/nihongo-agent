"""Chat a riga di comando con l'agente v1 (LangGraph). Scrivi 'esci' per uscire."""
import uuid
from pathlib import Path

from google import genai
from google.genai import errors
from langgraph.checkpoint.memory import InMemorySaver

from nihongo_agent.config import get_api_key, get_model_name
from nihongo_agent.graph import build_graph, run_turn_v1
from nihongo_agent.tools import get_dictionary
from nihongo_agent.tracing import TraceLog

LOG_PATH = Path(__file__).resolve().parent / "logs" / "traces_v1.jsonl"


def main() -> None:
    get_dictionary()  # se il file manca, l'errore arriva subito e chiaro
    client = genai.Client(api_key=get_api_key())
    model = get_model_name()
    trace = TraceLog(LOG_PATH, echo=True)
    graph = build_graph(client, model, trace=trace, checkpointer=InMemorySaver())
    thread_id = str(uuid.uuid4())  # una conversazione = un thread
    config = {"configurable": {"thread_id": thread_id}}
    print(f"Agente v1 pronto ({model}). Tracce in {LOG_PATH}. Scrivi 'esci' per uscire.")
    while True:
        try:
            text = input("\nTu> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"esci", "exit", "quit"}:
            break
        if not text:
            continue
        before = graph.get_state(config)  # fotografia della conversazione prima del turno
        try:
            print("\nAgente>", run_turn_v1(graph, thread_id, text))
        except errors.APIError as exc:
            # scarta il turno rotto: si riparte dall'ultimo checkpoint valido
            if before.values:
                graph.update_state(before.config, None) #riparte dalla fotografia salvata prima del turno
            else:
                thread_id = str(uuid.uuid4())
                config = {"configurable": {"thread_id": thread_id}}
            print(f"[errore API {exc.code}] {exc.message}")


if __name__ == "__main__":
    main()