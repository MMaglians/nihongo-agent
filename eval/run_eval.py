"""Esegue le domande di test: uv run python eval/run_eval.py"""
from pathlib import Path

from google import genai

from nihongo_agent.config import get_api_key, get_model_name
from nihongo_agent.evaluation import evaluate, new_results, read_questions, save_results
from nihongo_agent.tools import get_dictionary

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    get_dictionary()  # se il dizionario manca, l'errore arriva subito
    questions = read_questions(ROOT / "eval" / "questions_v0.txt")
    model = get_model_name()
    client = genai.Client(api_key=get_api_key())
    print(f"{len(questions)} domande, modello {model}. Servono circa 8-10 minuti.")
    rows = evaluate(client, model, questions)
    save_results(new_results(model, rows), ROOT / "eval" / "results_v0.json")
    print("Salvato eval/results_v0.json. Ora: uv run python eval/label.py")


if __name__ == "__main__":
    main()