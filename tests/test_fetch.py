import importlib.util
import io
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "fetch_jmdict", Path(__file__).resolve().parents[1] / "scripts" / "fetch_jmdict.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def test_pick_asset_chooses_eng_common():
    release = {"assets": [{"name": "jmdict-eng-3.6.2+2026.json.zip"},
                          {"name": "jmdict-eng-common-3.6.2+2026.json.zip"},
                          {"name": "jmdict-eng-common-3.6.2+2026.json.tgz"}]}
    assert fetch.pick_asset(release)["name"] == "jmdict-eng-common-3.6.2+2026.json.zip"
    with pytest.raises(RuntimeError, match="non trovato"):
        fetch.pick_asset({"assets": [{"name": "altro.zip"}]})


def test_extract_json_from_zip():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as z:
        z.writestr("jmdict-eng-common-3.6.2.json", '{"words": []}')
    assert fetch.extract_json(buffer.getvalue()) == b'{"words": []}'