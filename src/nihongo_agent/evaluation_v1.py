"""Valutazione della v1 (grafo): stesse metriche della v0 più rotta, chiamate e confronto appaiato."""
import json
import math
import statistics
import time
import uuid

from google.genai import errors
from langgraph.checkpoint.memory import InMemorySaver

from nihongo_agent.evaluation import PRICE_INPUT, PRICE_OUTPUT, tool_ok, wilson_interval
from nihongo_agent.graph import build_graph, run_turn_v1
from nihongo_agent.tracing import TraceLog

PRICE_EMBED = 0.15  # $ per milione di token in input, gemini-embedding-001 (Google Developers Blog)

EXPECTED_ROUTE = {
    "parola": "usa_tool", "lettura": "usa_tool", "assente": "usa_tool", "quiz": "usa_tool",
    "senza_tool": "rispondi", "appunti": "recupera", "appunti_assente": "recupera",
}
PRIVATE_CATEGORIES = {"appunti", "appunti_assente"}  # risposte con contenuto degli appunti


def run_question_v1(client, model: str, question: str, notes=None) -> dict:
    """Una domanda in un thread nuovo. Misura rotta, tool, chiamate, token, tempo."""
    trace = TraceLog()  # solo in memoria
    graph = build_graph(client, model, trace=trace, checkpointer=InMemorySaver(), notes=notes)
    started = time.perf_counter()
    answer = run_turn_v1(graph, str(uuid.uuid4()), question)
    seconds = round(time.perf_counter() - started, 2)
    events = trace.events
    model_events = [e for e in events if e["kind"] == "model"]
    tool_events = [e for e in events if e["kind"] == "tool"]
    routes = [e["route"] for e in events if e["kind"] == "route"]
    retrieved = [e for e in events if e["kind"] == "retrieve"]
    return {
        "answer": answer,
        "route": routes[0] if routes else None,
        "tools_called": [e["name"] for e in tool_events],
        "observations": [json.dumps(e["result"], ensure_ascii=False)[:400] for e in tool_events],
        "retrieved": retrieved[0] if retrieved else None,
        "calls": len(model_events),
        "input_tokens": sum(e.get("input_tokens") or 0 for e in model_events),
        "output_tokens": sum(e.get("output_tokens") or 0 for e in model_events),
        "thinking_tokens": sum(e.get("thinking_tokens") or 0 for e in model_events),
        "seconds": seconds,
        "hit_limit": any(e["kind"] == "limit" for e in events),
        "api_error": False,
    }


def _failed_result() -> dict:
    return {"answer": "", "route": None, "tools_called": [], "observations": [], "retrieved": None,
            "calls": 0, "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0,
            "seconds": 0.0, "hit_limit": False, "api_error": True}


def evaluate_v1(client, model: str, questions: list[dict], notes=None, *, pause: float = 20.0,
                sleep=time.sleep, log=print) -> list[dict]:
    """Come evaluate della v0: una conversazione nuova per domanda, un nuovo tentativo dopo 60 s."""
    rows = []
    for i, q in enumerate(questions, 1):
        result = None
        for attempt in (1, 2):
            try:
                result = run_question_v1(client, model, q["question"], notes)
                break
            except errors.APIError as exc:
                log(f"  domanda {i}: errore API {exc.code} (tentativo {attempt})")
                if attempt == 1:
                    sleep(60)
        result = result or _failed_result()
        expected_route = EXPECTED_ROUTE[q["category"]]
        ok_tool = tool_ok(q["expected_tool"], result["tools_called"]) and not result["api_error"]
        ok_route = result["route"] == expected_route
        rows.append({**q, **result, "expected_route": expected_route,
                     "tool_ok": ok_tool, "route_ok": ok_route, "answer_ok": None})
        log(f"{i:>2}/{len(questions)} [{q['category']}] rotta={result['route']} "
            f"tool_ok={ok_tool} chiamate={result['calls']}")
        sleep(pause)
    return rows


def sign_test(wins: int, losses: int) -> float:
    """Test dei segni a due code sulle coppie discordanti (binomiale con p = 0,5)."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    p = 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, p)


def paired(rows_v0: list[dict], rows_v1: list[dict], key: str) -> dict:
    """Confronto appaiato sulle domande comuni: quante migliorano, peggiorano, restano uguali."""
    v0 = {r["question"]: r for r in rows_v0}
    common = [r for r in rows_v1 if r["question"] in v0 and r[key] is not None and v0[r["question"]][key] is not None]
    better = sum(bool(r[key]) and not v0[r["question"]][key] for r in common)
    worse = sum(not r[key] and bool(v0[r["question"]][key]) for r in common)
    return {"n": len(common), "v1_better": better, "v1_worse": worse,
            "same": len(common) - better - worse, "p_value": round(sign_test(better, worse), 3)}


def summarize_v1(rows: list[dict], embed_tokens_per_question: float = 30.0) -> dict:
    n = len(rows)
    labeled = [r for r in rows if r["answer_ok"] is not None]
    count = lambda key, subset=rows: sum(bool(r[key]) for r in subset)  # noqa: E731
    inp = sum(r["input_tokens"] for r in rows)
    out = sum(r["output_tokens"] + r["thinking_tokens"] for r in rows)
    n_retrieve = sum(r["route"] == "recupera" for r in rows)
    cost = (inp * PRICE_INPUT + out * PRICE_OUTPUT
            + n_retrieve * embed_tokens_per_question * PRICE_EMBED) / 1_000_000
    return {
        "n": n,
        "tool_ok": count("tool_ok"), "tool_ci": wilson_interval(count("tool_ok"), n),
        "route_ok": count("route_ok"), "route_ci": wilson_interval(count("route_ok"), n),
        "labeled": len(labeled), "answer_ok": count("answer_ok", labeled),
        "answer_ci": wilson_interval(count("answer_ok", labeled), len(labeled)),
        "mean_calls": sum(r["calls"] for r in rows) / n if n else 0.0,
        "median_seconds": statistics.median(r["seconds"] for r in rows) if n else 0.0,
        "mean_input_tokens": inp / n if n else 0.0, "mean_output_tokens": out / n if n else 0.0,
        "hit_limit": count("hit_limit"), "api_errors": count("api_error"),
        "cost_usd_per_question": cost / n if n else 0.0,
    }


def by_category_v1(rows: list[dict]) -> dict[str, dict]:
    table: dict[str, dict] = {}
    for r in rows:
        c = table.setdefault(r["category"], {"n": 0, "route_ok": 0, "tool_ok": 0, "labeled": 0, "answer_ok": 0})
        c["n"] += 1
        c["route_ok"] += r["route_ok"]
        c["tool_ok"] += r["tool_ok"]
        if r["answer_ok"] is not None:
            c["labeled"] += 1
            c["answer_ok"] += r["answer_ok"]
    return table


def redact(data: dict) -> dict:
    """Versione pubblicabile: niente testo degli appunti nelle risposte e nei pezzi recuperati."""
    rows = []
    for r in data["rows"]:
        r = dict(r)
        if r["category"] in PRIVATE_CATEGORIES:
            r["answer"] = "[omessa: contenuto degli appunti privati]"
            if r.get("retrieved"):
                r["retrieved"] = {"scores": r["retrieved"].get("scores", [])}
        rows.append(r)
    return {**data, "rows": rows}