"""Stampa le metriche in Markdown: uv run python eval/report.py"""
from pathlib import Path

from nihongo_agent.evaluation import by_category, load_results, summarize

PATH = Path(__file__).resolve().parents[1] / "eval" / "results_v0.json"


def it(x: float, digits: int = 2) -> str:
    return f"{x:.{digits}f}".replace(".", ",")


def main() -> None:
    data = load_results(PATH)
    rows = data["rows"]
    s = summarize(rows)
    print(f"Modello: {data['model']}, data: {data['date']}, domande: {s['n']}\n")
    lo, hi = s["tool_ci"]
    print(f"- Tool corretto: {s['tool_ok']}/{s['n']} (IC 95% {it(lo)}–{it(hi)})")
    lo, hi = s["answer_ci"]
    print(f"- Risposta corretta (etichettate a mano {s['labeled']}/{s['n']}): "
          f"{s['answer_ok']}/{s['labeled']} (IC 95% {it(lo)}–{it(hi)})")
    print(f"- Passi medi: {it(s['mean_steps'])}; tempo medio: {it(s['mean_seconds'], 1)} s")
    print(f"- Token medi per domanda: {it(s['mean_input_tokens'], 0)} in, {it(s['mean_output_tokens'], 0)} out")
    print(f"- Costo: 0 $ sul tier gratuito; equivalente a pagamento "
          f"{it(s['cost_usd_per_question'], 5)} $ per domanda ({it(s['cost_usd_total'], 4)} $ in totale)")
    print(f"- Limite di passi raggiunto: {s['hit_limit']}; errori API: {s['api_errors']}\n")
    print("| Categoria | Domande | Tool corretto | Risposta corretta |")
    print("|---|---|---|---|")
    for cat, c in by_category(rows).items():
        print(f"| {cat} | {c['n']} | {c['tool_ok']}/{c['n']} | {c['answer_ok']}/{c['labeled']} |")
    wrong = [r for r in rows if not r["tool_ok"] or r["answer_ok"] is False]
    print(f"\nDomande da analizzare ({len(wrong)}):")
    for r in wrong:
        print(f"- [{r['category']}] {r['question']} (tool: {r['tools_called'] or 'nessuno'})")


if __name__ == "__main__":
    main()