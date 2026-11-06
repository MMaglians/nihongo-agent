"""Report della v1 e confronto con la v0: uv run python eval/report_v1.py"""
from pathlib import Path

from nihongo_agent.evaluation import load_results, save_results
from nihongo_agent.evaluation_v1 import by_category_v1, paired, redact, summarize_v1

ROOT = Path(__file__).resolve().parents[1]
FULL_PATH = ROOT / "data" / "results_v1_full.json"
PUBLIC_PATH = ROOT / "eval" / "results_v1.json"
V0_PATH = ROOT / "eval" / "results_v0.json"


def ci(interval) -> str:
    return f"{interval[0]:.2f}-{interval[1]:.2f}".replace(".", ",")


def main() -> None:
    data = load_results(FULL_PATH)
    rows = data["rows"]
    s = summarize_v1(rows)
    print(f"Modello {data['model']}, {data['date']}, {s['n']} domande, {s['labeled']} etichettate.\n")
    print("| Metrica | v1 |\n|---|---|")
    print(f"| Rotta corretta | {s['route_ok']}/{s['n']} (IC 95% {ci(s['route_ci'])}) |")
    print(f"| Tool corretto | {s['tool_ok']}/{s['n']} (IC 95% {ci(s['tool_ci'])}) |")
    print(f"| Risposta corretta | {s['answer_ok']}/{s['labeled']} (IC 95% {ci(s['answer_ci'])}) |")
    print(f"| Chiamate al modello (media) | {s['mean_calls']:.2f} |")
    print(f"| Secondi per domanda (mediana) | {s['median_seconds']:.1f} |")
    print(f"| Token per domanda (in / out) | {s['mean_input_tokens']:.0f} / {s['mean_output_tokens']:.0f} |")
    print(f"| Costo equivalente a pagamento | {s['cost_usd_per_question']:.5f} $ per domanda |")
    print(f"| Limite di passi / errori API | {s['hit_limit']} / {s['api_errors']} |")

    print("\n| Categoria | Domande | Rotta | Tool | Risposta |\n|---|---|---|---|---|")
    for cat, c in by_category_v1(rows).items():
        print(f"| {cat} | {c['n']} | {c['route_ok']}/{c['n']} | {c['tool_ok']}/{c['n']} | {c['answer_ok']}/{c['labeled']} |")

    if V0_PATH.exists():
        v0_rows = load_results(V0_PATH)["rows"]
        print("\nConfronto appaiato con la v0 (stesse domande, test dei segni):")
        print("| Metrica | Coppie | v1 meglio | v1 peggio | Uguali | p |\n|---|---|---|---|---|---|")
        for key, name in [("tool_ok", "Tool corretto"), ("answer_ok", "Risposta corretta")]:
            p = paired(v0_rows, rows, key)
            print(f"| {name} | {p['n']} | {p['v1_better']} | {p['v1_worse']} | {p['same']} | {p['p_value']} |")

    wrong = [r for r in rows if not r["route_ok"] or not r["tool_ok"] or r["answer_ok"] is False]
    print(f"\nDa analizzare ({len(wrong)} domande):")
    for r in wrong:
        print(f"- [{r['category']}] {r['question']} -> rotta {r['route']}, tool {r['tools_called']}, "
              f"risposta_ok {r['answer_ok']}")

    save_results(redact(data), PUBLIC_PATH)
    print(f"\nSalvato {PUBLIC_PATH} (senza testo degli appunti): questo si può pubblicare.")


if __name__ == "__main__":
    main()