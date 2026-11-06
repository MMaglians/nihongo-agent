"""Memoria dei progressi: risposte ai quiz salvate in SQLite, sopravvivono tra le sessioni."""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "progress.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS pending (
    word TEXT PRIMARY KEY, reading TEXT, options TEXT, correct TEXT
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY AUTOINCREMENT, time TEXT, word TEXT, reading TEXT,
    given TEXT, correct INTEGER
);
"""


class ProgressStore:
    def __init__(self, path: Path | str = DEFAULT_PATH):
        if str(path) != ":memory:": #crea database solo su RAM, usato nei test
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        # LangGraph può eseguire i nodi in un altro thread: per questo check_same_thread=False
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.executescript(SCHEMA)

    def add_pending(self, questions: list[dict]) -> None:
        """Ricorda le domande appena proposte, per correggerle in modo deterministico."""
        with self.db: #o vengono salvate tutte o nessuna
            for q in questions:
                self.db.execute(
                    "INSERT OR REPLACE INTO pending VALUES (?, ?, ?, ?)", # ? come parametri
                    (q["word"], q["reading"], json.dumps(q["options"], ensure_ascii=False), q["correct"]),
                )

    def check(self, word: str, letter: str) -> dict:
        """Confronta la lettera con quella giusta, salva l'esito, toglie la domanda dalle pendenti."""
        row = self.db.execute(
            "SELECT reading, options, correct FROM pending WHERE word = ?", (word.strip(),)
        ).fetchone()
        if row is None:
            return {"error": f"nessuna domanda di quiz in sospeso per '{word}'"}
        reading, options, correct = row[0], json.loads(row[1]), row[2]
        given = letter.strip().upper()[:1]
        ok = given == correct
        with self.db:
            self.db.execute(
                "INSERT INTO answers (time, word, reading, given, correct) VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(timespec="seconds"), word, reading, given, int(ok)),
            )
            self.db.execute("DELETE FROM pending WHERE word = ?", (word,))
        return {"correct": ok, "word": word, "reading": reading,
                "correct_letter": correct, "meaning": options[correct]}

    def to_review(self, n: int = 5) -> list[str]:
        """Parole sbagliate più volte di quante siano state indovinate."""
        rows = self.db.execute(
            "SELECT word FROM answers GROUP BY word HAVING SUM(1 - correct) > SUM(correct) "
            "ORDER BY SUM(1 - correct) DESC, MAX(time) DESC LIMIT ?", (n,)
        ).fetchall()
        return [r[0] for r in rows]

    def summary(self) -> dict:
        total, right = self.db.execute(
            "SELECT COUNT(*), COALESCE(SUM(correct), 0) FROM answers"
        ).fetchone()
        return {
            "answers": total,
            "correct": right,
            "accuracy": round(right / total, 2) if total else None,
            "to_review": self.to_review(),
        }