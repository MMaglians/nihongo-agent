"""Chiamata al modello con ritenti per gli errori temporanei del server."""
import time

from google.genai import errors


def generate_with_retry(client, *, model, contents, config,
                        tries=4, base_delay=2.0, sleep=time.sleep):
    """Riprova solo se il server è in difficoltà (503, 500...).

    Attese: 2 s, 4 s, 8 s. Gli errori 4xx (chiave sbagliata, quota esaurita)
    NON vengono ripetuti: ripeterli non li risolve.
    """
    for attempt in range(1, tries + 1):
        try:
            return client.models.generate_content(
                model=model, contents=contents, config=config
            )
        except errors.ServerError as exc:
            if attempt == tries:
                raise
            wait = base_delay * 2 ** (attempt - 1)
            print(f"[retry] errore {exc.code}, nuovo tentativo tra {wait:.0f} s")
            sleep(wait)