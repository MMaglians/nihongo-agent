"""Etichettatura a mano delle risposte della v1: uv run python eval/label_v1.py"""
from pathlib import Path

from nihongo_agent.evaluation import load_results, save_results

FULL_PATH = Path(__file__).resolve().parents[1] / "data" / "results_v1_full.json"


def main() -> None:
    data = load_results(FULL_PATH)
    todo = [r for r in data["rows"] if r["answer_ok"] is None]
    print(f"{len(todo)} risposte da etichettare. s = corretta, n = sbagliata, q = salva ed esci.")
    for i, row in enumerate(todo, 1):
        print("\n" + "=" * 70)
        print(f"[{i}/{len(todo)}] {row['category']} | rotta {row['route']} (attesa {row['expected_route']})"
              f" | tool {row['tools_called'] or 'nessuno'}")
        print(f"DOMANDA: {row['question']}")
        for obs in row["observations"]:
            print(f"  osservazione: {obs[:200]}")
        if row.get("retrieved"):
            print(f"  appunti: {row['retrieved'].get('sources')} punteggi {row['retrieved'].get('scores')}")
        print(f"RISPOSTA:\n{row['answer']}")
        while True:
            choice = input("Corretta? [s/n/q] ").strip().lower()
            if choice in {"s", "n", "q"}:
                break
        if choice == "q":
            break
        row["answer_ok"] = choice == "s"
        save_results(data, FULL_PATH)  # salva dopo ogni etichetta: si può interrompere
    left = sum(r["answer_ok"] is None for r in data["rows"])
    print(f"\nMancano {left} etichette. Quando sono 0: uv run python eval/report_v1.py")


if __name__ == "__main__":
    main()