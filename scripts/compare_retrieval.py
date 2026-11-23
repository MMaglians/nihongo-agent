"""Confronta il retrieval locale (numpy) con Cosmos DB sulle 8 domande 'appunti' dell'eval v1."""
from pathlib import Path

from azure.cosmos import CosmosClient
from google import genai

from nihongo_agent.azure_config import setting
from nihongo_agent.azure_notes import CosmosNotesIndex, compare_hits
from nihongo_agent.config import get_api_key, get_embed_model_name
from nihongo_agent.evaluation import read_questions
from nihongo_agent.notes import NotesIndex, gemini_embedder

ROOT = Path(__file__).resolve().parents[1]
K = 4


def cached(embed):
    """Ogni domanda diventa un vettore una volta sola, poi la riusano entrambi gli indici."""
    memory = {}
    def wrapper(texts, task):
        missing = [t for t in texts if (t, task) not in memory]
        if missing:
            memory.update({(t, task): v for t, v in zip(missing, embed(missing, task))})
        return [memory[(t, task)] for t in texts]
    return wrapper


def main() -> None:
    client = genai.Client(api_key=get_api_key())
    embed_model = get_embed_model_name()
    embed = cached(gemini_embedder(client, embed_model))

    local, rebuilt = NotesIndex.load_or_build(embed, embed_model)
    print(f"Locale: {len(local.chunks)} pezzi ({'ricostruito' if rebuilt else 'dalla cache'}).")
    cosmos = CosmosClient(setting("COSMOS_ENDPOINT"), credential=setting("COSMOS_KEY"))
    container = cosmos.get_database_client(setting("COSMOS_DATABASE")).get_container_client(
        setting("COSMOS_CONTAINER"))
    remote = CosmosNotesIndex(container, embed)

    questions = [q["question"] for q in read_questions(ROOT / "eval" / "questions_v1.txt")
                 if q["category"].startswith("appunti")]
    rows = []
    for q in questions:
        row = compare_hits(local.search(q, K), remote.search(q, K))
        rows.append(row)
        print(f"- {q[:45]:<45} overlap {row['overlap']}/{K}  ordine uguale: {row['same_order']}  "
              f"max |Δcos| {row['max_score_diff']}")
    n = len(rows)
    print(f"\nStessi {K} pezzi: {sum(r['same_set'] for r in rows)}/{n}; "
          f"stesso ordine: {sum(r['same_order'] for r in rows)}/{n}; "
          f"max |Δcos| complessivo: {max(r['max_score_diff'] for r in rows)}")


if __name__ == "__main__":
    main()