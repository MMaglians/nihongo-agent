"""Log delle tracce: una riga JSON per evento, in un file .jsonl."""
import json
from datetime import datetime
from pathlib import Path


class TraceLog:
    def __init__(self, path: Path | None = None, echo: bool = False):
        self.path = path
        self.echo = echo
        self.events: list[dict] = []  # copia in memoria, la usa la valutazione
        if path is not None:
            Path(path).parent.mkdir(parents=True, exist_ok=True)

    def event(self, kind: str, **data) -> None:
        record = {"time": datetime.now().isoformat(timespec="seconds"), "kind": kind, **data}
        self.events.append(record)
        if self.path is not None:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        if self.echo and kind in ("tool", "limit", "error"):
            detail = {k: v for k, v in data.items() if k != "step"}
            print(f"  [{kind}] {json.dumps(detail, ensure_ascii=False)[:300]}")