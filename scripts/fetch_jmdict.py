"""Scarica JMdict (inglese, solo parole comuni) in data/jmdict-eng-common.json.

Fonte: https://github.com/scriptin/jmdict-simplified (file derivati da JMdict,
licenza CC BY-SA 4.0, (c) EDRDG). Il file NON va messo su GitHub.
"""
import io
import json
import urllib.request
import zipfile
from pathlib import Path

API = "https://api.github.com/repos/scriptin/jmdict-simplified/releases/latest"
OUT = Path(__file__).resolve().parents[1] / "data" / "jmdict-eng-common.json"


def pick_asset(release: dict) -> dict:
    """Sceglie il file 'jmdict-eng-common-...json.zip' tra quelli della release."""
    names = []
    for asset in release["assets"]:
        names.append(asset["name"])
        if asset["name"].startswith("jmdict-eng-common-") and asset["name"].endswith(".json.zip"):
            return asset
    raise RuntimeError(f"File jmdict-eng-common non trovato. Disponibili: {names}")


def extract_json(zip_bytes: bytes) -> bytes:
    """Estrae il primo file .json dallo zip, tutto in memoria."""
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        names = [n for n in archive.namelist() if n.endswith(".json")]
        if not names:
            raise RuntimeError("Nessun file .json dentro lo zip")
        return archive.read(names[0])


def fetch(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "nihongo-agent"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.read()


def main() -> None:
    release = json.loads(fetch(API))
    asset = pick_asset(release)
    print(f"Scarico {asset['name']} ({asset['size'] / 1e6:.1f} MB)...")
    data = extract_json(fetch(asset["browser_download_url"]))
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes(data)
    meta = json.loads(data)
    print(f"Salvato {OUT}: {len(meta['words'])} parole, dizionario del {meta['dictDate']}")


if __name__ == "__main__":
    main()