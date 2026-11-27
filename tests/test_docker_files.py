"""Regole di sicurezza dell'immagine, controllate come test: se qualcuno le rompe, la CI fallisce."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def lines(name: str) -> list[str]:
    return [line.strip() for line in (ROOT / name).read_text(encoding="utf-8").splitlines()]


def test_dockerignore_keeps_secrets_and_private_data_out():
    ignored = set(lines(".dockerignore"))
    for entry in [".env", "notes/", "notes_draft/", "raw_notes/", "data/", "logs/", ".venv/", ".git/"]:
        assert entry in ignored, f"{entry} deve stare nel .dockerignore"


def test_dockerfile_runs_as_non_root_and_never_copies_env():
    dockerfile = lines("Dockerfile")
    assert any(line.startswith("USER ") and line != "USER root" for line in dockerfile)
    assert not any(line.startswith(("COPY", "ADD")) and ".env" in line for line in dockerfile)


def test_compose_takes_secrets_from_env_file_not_from_the_file_itself():
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    assert "env_file: .env" in compose
    assert "GEMINI_API_KEY:" not in compose and "GEMINI_API_KEY=" not in compose