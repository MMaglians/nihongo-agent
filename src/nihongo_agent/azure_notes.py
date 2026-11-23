"""RAG degli appunti su servizi Azure: appunti in Blob Storage, vettori in Cosmos DB.

CosmosNotesIndex ha lo stesso metodo search() di NotesIndex: il grafo non cambia.
"""
from pathlib import Path

DIM = 768  # come gemini_embedder in notes.py


# --- Blob Storage ---------------------------------------------------------------------------
def sync_notes(container, folder) -> tuple[int, int]:
    """Rende il container uguale a `folder`: carica i .md/.txt e cancella i blob che non ci sono più.

    Ritorna (caricati, cancellati). Il nome del blob è il percorso relativo, con le barre /.
    """
    folder = Path(folder)
    names = set()
    for path in sorted(folder.rglob("*")):
        if path.is_file() and path.suffix.lower() in {".md", ".txt"}:
            name = path.relative_to(folder).as_posix()   # su Windows: barre / anche nei nomi
            container.upload_blob(name, path.read_bytes(), overwrite=True)
            names.add(name)
    stale = [b.name for b in container.list_blobs() if b.name not in names]
    for name in stale:
        container.delete_blob(name)
    return len(names), len(stale)


def download_notes(container, folder) -> int:
    """Scarica i .md/.txt del container in `folder`, mantenendo le sottocartelle."""
    count = 0
    for blob in container.list_blobs():
        if not blob.name.lower().endswith((".md", ".txt")):
            continue
        target = Path(folder) / blob.name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(container.download_blob(blob.name).readall())
        count += 1
    return count


# --- Cosmos DB ------------------------------------------------------------------------------
def vector_policies(dim: int = DIM) -> tuple[dict, dict]:
    """Dove sta il vettore e come si indicizza. Non si possono cambiare dopo la creazione."""
    embedding_policy = {"vectorEmbeddings": [
        {"path": "/embedding", "dataType": "float32", "distanceFunction": "cosine",
         "dimensions": dim}]}
    indexing_policy = {
        "includedPaths": [{"path": "/*"}],
        "excludedPaths": [{"path": '/"_etag"/?'}, {"path": "/embedding/*"}],
        "vectorIndexes": [{"path": "/embedding", "type": "diskANN"}],  # l'unico supportato dall'emulatore
    }
    return embedding_policy, indexing_policy


def create_notes_container(database, name: str, dim: int = DIM, reset: bool = False):
    """Crea il container dei vettori; con reset=True lo cancella e lo ricrea da zero."""
    from azure.cosmos import PartitionKey
    from azure.cosmos.exceptions import CosmosResourceNotFoundError
    if reset:
        try:
            database.delete_container(name)
        except CosmosResourceNotFoundError:
            pass
    embedding_policy, indexing_policy = vector_policies(dim)
    return database.create_container_if_not_exists(
        id=name, partition_key=PartitionKey(path="/id"),
        indexing_policy=indexing_policy, vector_embedding_policy=embedding_policy)


def to_items(chunks: list[dict], vectors) -> list[dict]:
    if len(chunks) != len(vectors):
        raise ValueError(f"{len(chunks)} pezzi ma {len(vectors)} vettori")
    return [{"id": f"chunk-{i:04d}", "source": c["source"], "text": c["text"],
             "embedding": [float(x) for x in v]}
            for i, (c, v) in enumerate(zip(chunks, vectors))]


SEARCH_QUERY = ("SELECT TOP {k} c.source, c.text, VectorDistance(c.embedding, @v) AS score "
                "FROM c ORDER BY VectorDistance(c.embedding, @v)")


class CosmosNotesIndex:
    """Come NotesIndex, ma i vettori stanno in un container Cosmos DB invece che in un JSON."""

    def __init__(self, container, embed):
        self.container = container
        self.embed = embed

    def search(self, query: str, k: int = 4) -> list[dict]:
        vector = [float(x) for x in self.embed([query], "RETRIEVAL_QUERY")[0]]
        rows = self.container.query_items(
            query=SEARCH_QUERY.format(k=int(k)), parameters=[{"name": "@v", "value": vector}],
            enable_cross_partition_query=True)
        hits = [{"source": r["source"], "text": r["text"], "score": round(float(r["score"]), 3)}
                for r in rows]
        # Coseno: più alto = più simile. Riordino comunque, per non dipendere dal verso dell'ORDER BY.
        return sorted(hits, key=lambda h: -h["score"])[:k]


# --- Confronto con l'indice locale -----------------------------------------------------------
def compare_hits(local_hits: list[dict], cloud_hits: list[dict]) -> dict:
    """Stessi pezzi? Stesso ordine? Quanto differiscono i coseni?"""
    def key(h):
        return (h["source"], h["text"])
    a, b = [key(h) for h in local_hits], [key(h) for h in cloud_hits]
    local_score = {key(h): h["score"] for h in local_hits}
    diffs = [abs(local_score[key(h)] - h["score"]) for h in cloud_hits if key(h) in local_score]
    return {"same_set": set(a) == set(b), "same_order": a == b,
            "overlap": len(set(a) & set(b)), "max_score_diff": round(max(diffs, default=0.0), 3)}