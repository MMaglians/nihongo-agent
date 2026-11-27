"""Quale indice degli appunti usa la chat: locale (file JSON) o Cosmos DB.

Si sceglie con NOTES_BACKEND=local (default) oppure NOTES_BACKEND=cosmos.
I due indici hanno lo stesso metodo search(): il grafo non cambia.
"""
import os

from nihongo_agent.azure_notes import CosmosNotesIndex
from nihongo_agent.notes import NotesIndex

BACKENDS = ("local", "cosmos")
EMPTY = "lancia prima scripts/index_notes_cosmos.py"


def count_items(container) -> int:
    rows = container.query_items("SELECT VALUE COUNT(1) FROM c", enable_cross_partition_query=True)
    return next(iter(rows))


def make_notes_index(embed, embed_model: str, backend: str | None = None, container=None):
    """Ritorna (indice, descrizione da stampare)."""
    backend = (backend or os.getenv("NOTES_BACKEND", "local")).strip().lower()
    if backend == "local":
        index, rebuilt = NotesIndex.load_or_build(embed, embed_model)
        state = "indice ricostruito" if rebuilt else "indice dalla cache"
        return index, f"locale, {len(index.chunks)} pezzi ({state})"
    if backend == "cosmos":
        from azure.cosmos.exceptions import CosmosResourceNotFoundError
        if container is None:
            from nihongo_agent.azure_config import notes_container
            container = notes_container()
        try:
            n = count_items(container)
        except CosmosResourceNotFoundError:
            raise RuntimeError(f"Database o container Cosmos inesistente: {EMPTY}") from None
        if n == 0:
            raise RuntimeError(f"Il container Cosmos è vuoto: {EMPTY}")
        return CosmosNotesIndex(container, embed), f"Cosmos DB, {n} pezzi"
    raise ValueError(f"NOTES_BACKEND={backend!r} non valido: usa uno tra {BACKENDS}")