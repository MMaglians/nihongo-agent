"""Indicizza gli appunti: Blob Storage -> pezzi -> embedding Gemini -> container Cosmos DB."""
import tempfile
import time
from pathlib import Path

from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from google import genai

from nihongo_agent.azure_config import setting
from nihongo_agent.azure_notes import create_notes_container, download_notes, to_items
from nihongo_agent.config import get_api_key, get_embed_model_name
from nihongo_agent.notes import NotesIndex, gemini_embedder, load_chunks


def main() -> None:
    # 1. Blob -> cartella temporanea: gli appunti non passano dal repository
    service = BlobServiceClient.from_connection_string(setting("AZURE_STORAGE_CONNECTION_STRING"))
    container = service.get_container_client(setting("AZURE_NOTES_CONTAINER"))
    with tempfile.TemporaryDirectory() as tmp:
        n_files = download_notes(container, tmp)
        chunks = load_chunks(Path(tmp))
    print(f"Blob: {n_files} file, {len(chunks)} pezzi.")
    if not chunks:
        raise SystemExit("Nessun pezzo: hai lanciato prima upload_notes_blob.py?")

    # 2. Embedding: stesso modello e stesso testo dell'indice locale
    client = genai.Client(api_key=get_api_key())
    embed_model = get_embed_model_name()
    vectors = NotesIndex.build(chunks, gemini_embedder(client, embed_model)).vectors

    # 3. Cosmos DB: database e container ricreati da zero, poi un item per pezzo
    cosmos = CosmosClient(setting("COSMOS_ENDPOINT"), credential=setting("COSMOS_KEY"))
    database = cosmos.create_database_if_not_exists(setting("COSMOS_DATABASE"))
    notes = create_notes_container(database, setting("COSMOS_CONTAINER"), reset=True)
    started = time.perf_counter()
    for item in to_items(chunks, vectors):
        notes.upsert_item(item)
    count = next(iter(notes.query_items("SELECT VALUE COUNT(1) FROM c",
                                        enable_cross_partition_query=True)))
    print(f"Cosmos: {count} item in '{notes.id}' ({embed_model}), "
          f"{time.perf_counter() - started:.1f} s per l'inserimento.")


if __name__ == "__main__":
    main()