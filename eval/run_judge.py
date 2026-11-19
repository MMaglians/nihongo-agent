"""Giudice LLM sulle 48 risposte già etichettate a mano (v0 e v1): uv run python eval/run_judge.py

Salva dopo ogni risposta (si riprende da dove si era fermato) in data/judge_full.json (privato)
e in eval/judge_results.json (pubblicabile: niente testo degli appunti).
"""
import time
from pathlib import Path

from google import genai

from nihongo_agent.config import get_api_key, get_embed_model_name, get_judge_model_name
from nihongo_agent.evaluation import load_results
from nihongo_agent.evaluation_v1 import PRIVATE_CATEGORIES
from nihongo_agent.judge import evidence_for, judge_row, public_rows, to_json
from nihongo_agent.notes import NotesIndex, gemini_embedder

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {"v0": ROOT / "eval" / "results_v0.json", "v1": ROOT / "data" / "results_v1_full.json"}
FULL_PATH = ROOT / "data" / "judge_full.json"
PUBLIC_PATH = ROOT / "eval" / "judge_results.json"
PAUSE_SECONDS = 6  # resta sotto le richieste al minuto del tier gratuito


def todo_rows(seen: set) -> list[tuple[str, dict]]:
    """Le risposte etichettate a mano non ancora giudicate, come (versione, riga)."""
    rows = []
    for name, path in SOURCES.items():
        rows += [(name, r) for r in load_results(path)["rows"] if (name, r["question"]) not in seen]
    return rows


def save(model: str, done: list[dict]) -> None:
    FULL_PATH.write_text(to_json({"model": model, "rows": done}), encoding="utf-8")
    PUBLIC_PATH.write_text(to_json({"model": model, "rows": public_rows(done, PRIVATE_CATEGORIES)}),
                           encoding="utf-8")


def main() -> None:
    client, model = genai.Client(api_key=get_api_key()), get_judge_model_name()
    embed_model = get_embed_model_name()
    notes, _ = NotesIndex.load_or_build(gemini_embedder(client, embed_model), embed_model)
    done = load_results(FULL_PATH)["rows"] if FULL_PATH.exists() else []
    todo = todo_rows({(r["set"], r["question"]) for r in done})
    print(f"Giudice {model}: {len(done)} già fatte, {len(todo)} da fare.")

    for name, row in todo:
        # Domande sugli appunti: contesto ricostruito con l'indice attuale (limite dichiarato).
        chunks = notes.search(row["question"], k=4) if row["category"] in PRIVATE_CATEGORIES else None
        try:
            verdict = judge_row(client, model, row, evidence_for(row, chunks))
        except Exception as exc:  # quota o rete: si salva ciò che è fatto e si riprende dopo
            print(f"Stop: {type(exc).__name__}: {exc}")
            break
        done.append({"set": name, "category": row["category"], "question": row["question"],
                     "human": row["answer_ok"], "judge": verdict["corretta"],
                     "motivazione": verdict["motivazione"]})
        save(model, done)
        print(f"{name} {row['category']:<15} umano={row['answer_ok']!s:<5} giudice={verdict['corretta']}")
        time.sleep(PAUSE_SECONDS)
    print(f"{len(done)} verdetti in {PUBLIC_PATH}")


if __name__ == "__main__":
    main()