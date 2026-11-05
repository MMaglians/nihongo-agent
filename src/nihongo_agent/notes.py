"""RAG sui tuoi appunti: lettura, chunking, embedding, ricerca per similarità coseno."""
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from google.genai import types

ROOT = Path(__file__).resolve().parents[2]
NOTES_DIR = ROOT / "notes"                      # appunti privati: cartella ignorata da Git
INDEX_PATH = ROOT / "data" / "notes_index.json"  # cache degli embedding: ignorata da Git
MAX_CHARS = 1000


def load_chunks(folder: Path = NOTES_DIR, max_chars: int = MAX_CHARS) -> list[dict]:
    """Ogni file .md/.txt diviso per titoli (#) e poi per paragrafi, fino a max_chars."""
    chunks = []
    for path in sorted(Path(folder).rglob("*")):
        if path.suffix.lower() not in {".md", ".txt"}:
            continue
        heading, buffer = path.stem, ""

        def flush():
            if buffer.strip():
                chunks.append({"source": f"{path.name} › {heading}", "text": buffer.strip()})

        for block in re.split(r"\n\s*\n", path.read_text(encoding="utf-8")):
            block = block.strip()
            if not block:
                continue
            if block.startswith("#"):          # nuovo titolo: chiude il pezzo precedente
                flush()
                buffer = ""
                first, _, rest = block.partition("\n")
                heading = first.lstrip("#").strip() or heading
                block = rest.strip()
                if not block:
                    continue
            if buffer and len(buffer) + len(block) > max_chars:
                flush()
                buffer = ""
            buffer = f"{buffer}\n\n{block}" if buffer else block
        flush()
    return chunks


def gemini_embedder(client, model: str, dim: int = 768, batch: int = 50):
    """Restituisce embed(testi, task) che chiama l'API a blocchi."""
    def embed(texts: list[str], task: str) -> list[list[float]]:
        vectors = []
        for i in range(0, len(texts), batch):
            response = client.models.embed_content(
                model=model, contents=texts[i:i + batch],
                config=types.EmbedContentConfig(task_type=task, output_dimensionality=dim),
            )
            vectors += [e.values for e in response.embeddings]
        return vectors
    return embed


def _normalize(matrix: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(matrix, axis=-1, keepdims=True)
    return matrix / np.where(norms == 0, 1, norms)


def _fingerprint(chunks: list[dict], model: str) -> str:
    raw = json.dumps([model, chunks], ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class NotesIndex:
    def __init__(self, chunks: list[dict], vectors, embed):
        self.chunks = chunks
        matrix = np.asarray(vectors, dtype=np.float32)
        self.vectors = _normalize(matrix.reshape(len(chunks), -1)) if len(chunks) else matrix
        self.embed = embed

    @classmethod
    def build(cls, chunks: list[dict], embed) -> "NotesIndex":
        texts = [f"{c['source']}\n{c['text']}" for c in chunks]
        vectors = embed(texts, "RETRIEVAL_DOCUMENT") if chunks else []
        return cls(chunks, vectors, embed)

    @classmethod
    def load_or_build(cls, embed, model: str, folder: Path = NOTES_DIR,
                      path: Path = INDEX_PATH) -> tuple["NotesIndex", bool]:
        """Riusa la cache se gli appunti e il modello non sono cambiati. Ritorna (indice, ricostruito?)."""
        chunks = load_chunks(folder)
        fingerprint = _fingerprint(chunks, model)
        if Path(path).exists():
            cached = json.loads(Path(path).read_text(encoding="utf-8"))
            if cached.get("fingerprint") == fingerprint:
                return cls(cached["chunks"], cached["vectors"], embed), False
        index = cls.build(chunks, embed)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps({"fingerprint": fingerprint, "model": model,
                                          "chunks": chunks, "vectors": index.vectors.tolist()}),
                              encoding="utf-8")
        return index, True

    def search(self, query: str, k: int = 4) -> list[dict]:
        """I k pezzi più simili alla domanda, con il punteggio coseno."""
        if not self.chunks:
            return []
        q = _normalize(np.asarray(self.embed([query], "RETRIEVAL_QUERY")[0], dtype=np.float32))
        scores = self.vectors @ q
        best = np.argsort(-scores)[:k]
        return [{**self.chunks[i], "score": round(float(scores[i]), 3)} for i in best]