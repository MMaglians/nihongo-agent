"""Stesse domande, due backend degli appunti, stessa sessione: il confronto che isola il backend."""
import random

from nihongo_agent.evaluation_v1 import paired, summarize_v1


def run_interleaved(questions: list[dict], indexes: dict, run_one, seed: int = 8) -> list[dict]:
    """Per ogni domanda un run per backend, uno subito dopo l'altro (meno deriva nel tempo).

    run_one(domanda, indice) -> riga di risultati. Le righe escono mescolate con un seme fisso,
    così l'etichettatura a mano non sa quale backend ha prodotto la risposta (alla cieca).
    """
    rows = []
    for question in questions:
        for name, index in indexes.items():
            rows.append({**run_one(question, index), "backend": name})
    random.Random(seed).shuffle(rows)
    return rows


def compare_backends(rows: list[dict], base: str = "local", other: str = "cosmos") -> dict:
    """Riassunto per backend, confronto appaiato e quante volte i pezzi recuperati coincidono."""
    a = [r for r in rows if r["backend"] == base]
    b = [r for r in rows if r["backend"] == other]
    by_question = {r["question"]: r for r in a}
    pairs = [(by_question[r["question"]], r) for r in b
             if r["question"] in by_question and r.get("retrieved") and by_question[r["question"]].get("retrieved")]
    same = sum(x["retrieved"].get("sources") == y["retrieved"].get("sources") for x, y in pairs)
    return {
        "summary": {base: summarize_v1(a), other: summarize_v1(b)},
        "route": paired(a, b, "route_ok"),      # "v1_better" qui significa: other meglio di base
        "answer": paired(a, b, "answer_ok"),
        "retrieval_pairs": len(pairs), "same_sources": same,
    }