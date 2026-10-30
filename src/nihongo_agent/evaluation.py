"""Valutazione dell'agente: esegue le domande di test e calcola le metriche."""
import json
import math
import time
from datetime import date
from pathlib import Path

from google.genai import errors

from nihongo_agent.agent import run_turn
from nihongo_agent.tracing import TraceLog

VALID_TOOLS = {"lookup_word", "make_quiz", "none"}
# Dollari per milione di token, Gemini 3.5 Flash-Lite a pagamento (pagina prezzi di Google, 30/10/2026).
# Sul tier gratuito il costo reale è 0: serve per stimare quanto costerebbe.
PRICE_INPUT, PRICE_OUTPUT = 0.30, 2.50

def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Intervallo di confidenza di Wilson (95%) per una proporzione."""
    if n == 0:
        return (0.0, 1.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - half), min(1.0, center + half))

def read_questions(path: Path) -> list[dict]:
    """Righe 'categoria | tool_atteso | domanda'. Righe vuote e con # sono ignorate."""
    questions = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|", 2)]
        if len(parts) != 3 or parts[1] not in VALID_TOOLS or not parts[2]:
            raise ValueError(f"riga non valida: {line!r}")
        questions.append({"category": parts[0], "expected_tool": parts[1], "question": parts[2]})
    return questions

def tool_ok(expected: str, called: list[str]) -> bool:
    """Il tool giusto, e solo quello (più chiamate allo stesso tool vanno bene)."""
    return set(called) == (set() if expected == "none" else {expected})

def run_question(client, model: str, question: str, max_steps: int = 6) -> dict:
    """Una domanda in una conversazione nuova. Misura tool, passi, token, tempo."""
    trace = TraceLog()  # solo in memoria
    started = time.perf_counter()
    answer = run_turn(client, model, [], question, max_steps=max_steps, trace=trace)
    seconds = round(time.perf_counter() - started, 2)
    model_events = [e for e in trace.events if e["kind"] == "model"]
    tool_events = [e for e in trace.events if e["kind"] == "tool"]
    return {
        "answer": answer,
        "tools_called": [e["name"] for e in tool_events],
        "observations": [json.dumps(e["result"], ensure_ascii=False)[:400] for e in tool_events],
        "steps": len(model_events),
        "input_tokens": sum(e.get("input_tokens") or 0 for e in model_events),
        "output_tokens": sum(e.get("output_tokens") or 0 for e in model_events),
        "thinking_tokens": sum(e.get("thinking_tokens") or 0 for e in model_events),
        "seconds": seconds,
        "hit_limit": any(e["kind"] == "limit" for e in trace.events),
        "api_error": False,
    }
    
def _failed_result() -> dict:
    return {"answer": "", "tools_called": [], "observations": [], "steps": 0, "input_tokens": 0,
            "output_tokens": 0, "thinking_tokens": 0, "seconds": 0.0, "hit_limit": False,
            "api_error": True}
    
def evaluate(client, model: str, questions: list[dict], *, pause: float = 20.0,
             sleep=time.sleep, log=print) -> list[dict]:
    """Esegue tutte le domande. La pausa tiene il ritmo sotto il limite al minuto."""
    rows = []
    for i, q in enumerate(questions, 1):
        result = None
        for attempt in (1, 2):
            try:
                result = run_question(client, model, q["question"])
                break
            except errors.APIError as exc:
                log(f"  domanda {i}: errore API {exc.code} (tentativo {attempt})")
                if attempt == 1:
                    sleep(60)
        result = result or _failed_result()
        ok = tool_ok(q["expected_tool"], result["tools_called"]) and not result["api_error"]
        rows.append({**q, **result, "tool_ok": ok, "answer_ok": None})
        log(f"{i:>2}/{len(questions)} [{q['category']}] tool_ok={ok} passi={result['steps']}")
        sleep(pause)
    return rows

def save_results(data: dict, path: Path) -> None:
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_results(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def new_results(model: str, rows: list[dict]) -> dict:
    return {"model": model, "date": date.today().isoformat(), "rows": rows}


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    labeled = [r for r in rows if r["answer_ok"] is not None]
    tools_ok = sum(r["tool_ok"] for r in rows)
    answers_ok = sum(r["answer_ok"] for r in labeled)
    inp = sum(r["input_tokens"] for r in rows)
    out = sum(r["output_tokens"] + r["thinking_tokens"] for r in rows)
    cost = (inp * PRICE_INPUT + out * PRICE_OUTPUT) / 1_000_000
    mean = lambda key: sum(r[key] for r in rows) / n if n else 0.0
    return {
        "n": n, "tool_ok": tools_ok, "tool_ci": wilson_interval(tools_ok, n),
        "labeled": len(labeled), "answer_ok": answers_ok,
        "answer_ci": wilson_interval(answers_ok, len(labeled)),
        "mean_steps": mean("steps"), "mean_seconds": mean("seconds"),
        "mean_input_tokens": inp / n if n else 0.0, "mean_output_tokens": out / n if n else 0.0,
        "hit_limit": sum(r["hit_limit"] for r in rows), "api_errors": sum(r["api_error"] for r in rows),
        "cost_usd_total": cost, "cost_usd_per_question": cost / n if n else 0.0,
    }
    
def by_category(rows: list[dict]) -> dict[str, dict]:
    table: dict[str, dict] = {}
    for r in rows:
        c = table.setdefault(r["category"], {"n": 0, "tool_ok": 0, "labeled": 0, "answer_ok": 0})
        c["n"] += 1
        c["tool_ok"] += r["tool_ok"]
        if r["answer_ok"] is not None:
            c["labeled"] += 1
            c["answer_ok"] += r["answer_ok"]
    return table