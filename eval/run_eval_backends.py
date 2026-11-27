"""Le 8 domande sugli appunti con backend locale e Cosmos, intercalate: uv run python eval/run_eval_backends.py

Prima: docker compose up -d azurite cosmos (e container Cosmos già indicizzato).
Risultati completi, privati e mescolati per l'etichettatura alla cieca: data/results_backends_full.json
"""
from pathlib import Path

from google import genai

from nihongo_agent.backend_eval import run_interleaved
from nihongo_agent.config import get_api_key, get_embed_model_name, get_model_name
from nihongo_agent.evaluation import new_results, read_questions, save_results
from nihongo_agent.evaluation_v1 import PRIVATE_CATEGORIES, evaluate_v1
from nihongo_agent.notes import gemini_embedder
from nihongo_agent.notes_backend import make_notes_index

ROOT = Path(__file__).resolve().parents[1]
FULL_PATH = ROOT / "data" / "results_backends_full.json"


def main() -> None:
    if FULL_PATH.exists():
        raise SystemExit(f"{FULL_PATH} esiste già (forse già etichettato): rinominalo per rifare il run.")
    questions = [q for q in read_questions(ROOT / "eval" / "questions_v1.txt")
                 if q["category"] in PRIVATE_CATEGORIES]
    model = get_model_name()
    client = genai.Client(api_key=get_api_key())
    embed_model = get_embed_model_name()
    embed = gemini_embedder(client, embed_model)
    indexes = {}
    for backend in ("local", "cosmos"):
        indexes[backend], description = make_notes_index(embed, embed_model, backend=backend)
        print(f"{backend}: {description}")
    print(f"{len(questions)} domande x {len(indexes)} backend, modello {model}. Circa 7 minuti.")

    def run_one(question, notes):
        return evaluate_v1(client, model, [question], notes)[0]

    rows = run_interleaved(questions, indexes, run_one)
    FULL_PATH.parent.mkdir(exist_ok=True)
    save_results(new_results(model, rows), FULL_PATH)
    print(f"Salvato {FULL_PATH}. Ora: uv run python eval/label_v1.py {FULL_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()