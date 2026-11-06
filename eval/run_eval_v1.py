"""Esegue le domande di test sulla v1: uv run python eval/run_eval_v1.py"""
from pathlib import Path

from google import genai

from nihongo_agent.config import get_api_key, get_embed_model_name, get_model_name
from nihongo_agent.evaluation import new_results, read_questions, save_results
from nihongo_agent.evaluation_v1 import evaluate_v1
from nihongo_agent.notes import NotesIndex, gemini_embedder
from nihongo_agent.tools import get_dictionary

ROOT = Path(__file__).resolve().parents[1]
FULL_PATH = ROOT / "data" / "results_v1_full.json"  # privato: contiene testo degli appunti


def main() -> None:
    get_dictionary()  # se il dizionario manca, l'errore arriva subito
    questions = read_questions(ROOT / "eval" / "questions_v1.txt")
    model = get_model_name()
    client = genai.Client(api_key=get_api_key())
    embed_model = get_embed_model_name()
    notes, _ = NotesIndex.load_or_build(gemini_embedder(client, embed_model), embed_model)
    print(f"{len(questions)} domande, modello {model}, {len(notes.chunks)} pezzi di appunti. "
          "Servono circa 15 minuti.")
    rows = evaluate_v1(client, model, questions, notes)
    FULL_PATH.parent.mkdir(exist_ok=True)
    save_results(new_results(model, rows), FULL_PATH)
    print(f"Salvato {FULL_PATH}. Ora: uv run python eval/label_v1.py")


if __name__ == "__main__":
    main()