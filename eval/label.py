"""Etichetta a mano le risposte: uv run python eval/label.py (puoi uscire e riprendere)."""
from pathlib import Path

from nihongo_agent.evaluation import load_results, save_results

PATH = Path(__file__).resolve().parents[1] / "eval" / "results_v0.json"


def main() -> None:
    data = load_results(PATH)
    rows = data["rows"]
    for i, row in enumerate(rows, 1):
        if row["answer_ok"] is not None:
            continue
        print(f"\n--- {i}/{len(rows)}  [{row['category']}]  atteso: {row['expected_tool']}"
              f"  chiamati: {row['tools_called'] or 'nessuno'}")
        print("Domanda:  ", row["question"])
        for obs in row["observations"]:
            print("Dizionario:", obs)
        print("Risposta: ", row["answer"])
        choice = ""
        while choice not in {"s", "n", "q"}:
            choice = input("Corretta secondo i criteri? s = sì, n = no, q = esci e salva > ").strip().lower()
        if choice == "q":
            break
        row["answer_ok"] = choice == "s"
        save_results(data, PATH)  # salva a ogni risposta
    done = sum(r["answer_ok"] is not None for r in rows)
    print(f"\nEtichettate {done}/{len(rows)}.")


if __name__ == "__main__":
    main()