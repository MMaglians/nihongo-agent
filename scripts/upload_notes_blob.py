"""Sincronizza la cartella notes/ con il container Blob (Azurite in locale)."""
from pathlib import Path

from azure.storage.blob import BlobServiceClient

from nihongo_agent.azure_config import setting
from nihongo_agent.azure_notes import sync_notes

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    service = BlobServiceClient.from_connection_string(setting("AZURE_STORAGE_CONNECTION_STRING"))
    container = service.get_container_client(setting("AZURE_NOTES_CONTAINER"))
    if not container.exists():
        container.create_container()   # privato per default: nessun accesso anonimo
    uploaded, deleted = sync_notes(container, ROOT / "notes")
    total = sum(1 for _ in container.list_blobs())
    print(f"'{container.container_name}' su {service.url}: {uploaded} caricati, "
          f"{deleted} cancellati, {total} blob in totale.")


if __name__ == "__main__":
    main()