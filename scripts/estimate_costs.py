"""Costo mensile stimato su Azure, per scenario: uv run python scripts/estimate_costs.py

Legge docs/cost_inputs.json e stampa una tabella Markdown da copiare in docs/COSTS.md.
What-if senza toccare il file: --sessions-per-replica 10 (es. chat esposta come API HTTP).
"""
import argparse
import json
from pathlib import Path

from nihongo_agent.costs import COMPONENTS, monthly_costs

ROOT = Path(__file__).resolve().parents[1]


def money(value: float) -> str:
    return f"{value:,.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sessions-per-replica", type=float, help="sostituisce il valore del file")
    args = parser.parse_args()
    inputs = json.loads((ROOT / "docs" / "cost_inputs.json").read_text(encoding="utf-8"))
    if args.sessions_per_replica:
        inputs["usage"]["sessions_per_replica"] = args.sessions_per_replica
        print(f"WHAT-IF: sessions_per_replica = {args.sessions_per_replica:g}")
    scenarios = inputs["scenarios"]
    results = {name: monthly_costs(inputs, n) for name, n in scenarios.items()}
    cur = inputs["currency"]
    print(f"Prezzi letti il {inputs['prices_read_on']}, {inputs['region']}, {cur} al mese.\n")
    print("| Componente | " + " | ".join(f"{k} ({v} studenti)" for k, v in scenarios.items()) + " |")
    print("|---|" + "---|" * len(scenarios))
    for part in COMPONENTS:
        print(f"| {part} | " + " | ".join(money(r["parts"][part]) for r in results.values()) + " |")
    print("| **Totale** | " + " | ".join(f"**{money(r['total'])}**" for r in results.values()) + " |")
    print("| Per studente | " + " | ".join(money(r["per_learner"]) for r in results.values()) + " |")
    print("| Domande al mese | " + " | ".join(f"{r['questions']:,}" for r in results.values()) + " |")
    print("| vCPU-secondi al mese (gratis fino a 180.000) | "
          + " | ".join(f"{r['vcpu_seconds']:,.0f}" for r in results.values()) + " |")
    worst = {name: monthly_costs(inputs, n, ru_factor=10)["total"] for name, n in scenarios.items()}
    print("\nSensibilità, RU per ricerca x10: " + "; ".join(f"{k} {money(v)}" for k, v in worst.items()))


if __name__ == "__main__":
    main()