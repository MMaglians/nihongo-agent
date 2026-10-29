"""Dizionario JMdict (formato jmdict-simplified): ricerca di parole e domande da quiz."""
import json
import random
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "jmdict-eng-common.json"


class Dictionary:
    def __init__(self, data: dict, seed: int | None = None):
        self.tags = data.get("tags", {})  # codice -> descrizione, es. "v1" -> "Ichidan verb"
        self.words = data["words"]
        self.rng = random.Random(seed)
        self.index: dict[str, list[dict]] = {}
        for word in self.words:
            for form in word["kanji"] + word["kana"]:
                entries = self.index.setdefault(form["text"], [])
                if not entries or entries[-1] is not word:
                    entries.append(word)
        self._pool = [w for w in self.words if 0 < len(self._first_gloss(w)) <= 40]

    @classmethod
    def from_file(cls, path: Path = DEFAULT_PATH, seed: int | None = None) -> "Dictionary":
        if not Path(path).exists():
            raise FileNotFoundError(
                f"{path} non trovato: esegui 'uv run python scripts/fetch_jmdict.py'"
            )
        with open(path, encoding="utf-8") as f:
            return cls(json.load(f), seed)

    @staticmethod
    def _glosses(sense: dict) -> list[str]:
        return [g["text"] for g in sense["gloss"] if g["lang"] == "eng"]

    def _first_gloss(self, word: dict) -> str:
        for sense in word["sense"]:
            glosses = self._glosses(sense)
            if glosses:
                return glosses[0]
        return ""

    def _summary(self, word: dict) -> dict:
        senses = []
        for sense in word["sense"][:3]:
            glosses = self._glosses(sense)
            if glosses:
                pos = [self.tags.get(t, t) for t in sense["partOfSpeech"]]
                senses.append({"pos": pos, "meanings": glosses[:4]})
        return {
            "kanji": [k["text"] for k in word["kanji"]],
            "readings": [k["text"] for k in word["kana"]],
            "common": any(f["common"] for f in word["kanji"] + word["kana"]),
            "senses": senses,
        }

    def lookup(self, text: str, max_entries: int = 3) -> list[dict]:
        """Cerca per forma scritta (kanji) o per lettura (kana). Lista vuota se assente."""
        return [self._summary(w) for w in self.index.get(text.strip(), [])[:max_entries]]

    def quiz(self, n: int) -> list[dict]:
        """n domande a scelta multipla: parola giapponese -> significato in inglese."""
        if len({self._first_gloss(w) for w in self._pool}) < 4:
            raise ValueError("dizionario troppo piccolo per un quiz")
        questions = []
        for word in self.rng.sample(self._pool, min(n, len(self._pool))):
            correct = self._first_gloss(word)
            wrong: list[str] = []
            while len(wrong) < 3:
                other = self._first_gloss(self.rng.choice(self._pool))
                if other != correct and other not in wrong:
                    wrong.append(other)
            options = wrong + [correct]
            self.rng.shuffle(options)
            letters = "ABCD"
            questions.append({
                "word": (word["kanji"] or word["kana"])[0]["text"],
                "reading": word["kana"][0]["text"],
                "options": dict(zip(letters, options)),
                "correct": letters[options.index(correct)],
            })
        return questions