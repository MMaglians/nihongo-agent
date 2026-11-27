"""Report del confronto tra backend: uv run python eval/report_backends.py"""
from pathlib import Path

from nihongo_agent.backend_eval import compare_backends
from nihongo_agent.evaluation import load_results, save_results
from nihongo_agent.evaluation_v1 import redact

ROOT = Path(__file__).resolve().parents[1]
FULL_PATH = ROOT / "data" / "results_backends_full.json"
PUBLIC_PATH = ROOT / "eval" / "results_backends.json"


def ci(interval) -> str:
    return f"{interval[0]:.2f}-{interval[1]:.2f}".replace(".", ",")


def main() -> None:
    data = load_results(FULL_PATH)
    missing = sum(r["answer_ok"] is None for r in data["rows"])
    if missing:
        raise SystemExit(f"Mancano {missing} etichette: uv run python eval/label_v1.py data/results_backends_full.json")
    c = compare_backends(data["rows"])
    print(f"Modello {data['model']}, {data['date']}, domande sugli appunti, stessa sessione.\n")
    print("| Metrica | Locale (numpy) | Cosmos DB (emulatore) |\n|---|---|---|")
    s, t = c["summary"]["local"], c["summary"]["cosmos"]
    print(f"| Rotta corretta | {s['route_ok']}/{s['n']} (IC {ci(s['route_ci'])}) | {t['route_ok']}/{t['n']} (IC {ci(t['route_ci'])}) |")
    print(f"| Risposta corretta | {s['answer_ok']}/{s['labeled']} (IC {ci(s['answer_ci'])}) | {t['answer_ok']}/{t['labeled']} (IC {ci(t['answer_ci'])}) |")
    print(f"| Secondi per domanda (mediana) | {s['median_seconds']:.1f} | {t['median_seconds']:.1f} |")
    print(f"| Token per domanda (in / out) | {s['mean_input_tokens']:.0f} / {s['mean_output_tokens']:.0f} | {t['mean_input_tokens']:.0f} / {t['mean_output_tokens']:.0f} |")
    print(f"| Errori API | {s['api_errors']} | {t['api_errors']} |")
    print("\nConfronto appaiato (test dei segni sulle coppie discordanti):")
    print("| Metrica | Coppie | Cosmos meglio | Cosmos peggio | Uguali | p |\n|---|---|---|---|---|---|")
    for key, name in [("route", "Rotta corretta"), ("answer", "Risposta corretta")]:
        p = c[key]
        print(f"| {name} | {p['n']} | {p['v1_better']} | {p['v1_worse']} | {p['same']} | {p['p_value']} |")
    print(f"\nStessi pezzi recuperati: {c['same_sources']}/{c['retrieval_pairs']} "
          "(domande instradate su 'recupera' con entrambi i backend)")
    save_results(redact(data), PUBLIC_PATH)
    print(f"\nSalvato {PUBLIC_PATH} (senza testo degli appunti).")


if __name__ == "__main__":
    main()