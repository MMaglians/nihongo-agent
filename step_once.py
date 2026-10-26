"""Script di prova: uv run python step_once.py "Che cosa vuol dire 猫?" """
import sys

from google import genai

from nihongo_agent.config import get_api_key, get_model_name
from nihongo_agent.one_step import ask_once


def main() -> None:
    question = sys.argv[1] if len(sys.argv) > 1 else "Che cosa vuol dire 食べる?"
    client = genai.Client(api_key=get_api_key())
    model = get_model_name()
    print(f"[modello] {model}")
    answer, trace = ask_once(client, model, question)
    for line in trace:
        print(f"[traccia] {line}")
    print(f"\n[risposta] {answer}")


if __name__ == "__main__":
    main()