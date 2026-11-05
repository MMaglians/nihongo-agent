"""Tool della v1: quelli della v0 più la memoria dei progressi. La v0 resta invariata."""
from google.genai import types

from nihongo_agent.progress import ProgressStore
from nihongo_agent.tools import LOOKUP_WORD_DECL, get_dictionary, lookup_word

_progress: ProgressStore | None = None


def get_progress() -> ProgressStore:
    """Apre il database dei progressi la prima volta che serve."""
    global _progress
    if _progress is None:
        _progress = ProgressStore()
    return _progress


def set_progress(store: ProgressStore | None) -> None:
    """Serve ai test: permette di usare un database in memoria."""
    global _progress
    _progress = store


def make_quiz_v1(n: int = 3, review: bool = False) -> dict:
    """Come make_quiz, ma ricorda le domande e, se review, ripassa le parole sbagliate."""
    n = max(1, min(int(n), 10))
    words = get_progress().to_review(n) if review else None
    questions = get_dictionary().quiz(n, words=words)
    get_progress().add_pending(questions)
    return {"questions": questions, "review": bool(words)}


def check_answer(word: str, letter: str) -> dict:
    """Corregge la risposta a una domanda del quiz e la salva nei progressi."""
    return get_progress().check(word, letter)


def show_progress() -> dict:
    """Riassunto dei progressi: risposte, accuratezza, parole da ripassare."""
    return get_progress().summary()


MAKE_QUIZ_V1_DECL = types.FunctionDeclaration(
    name="make_quiz",
    description=(
        "Genera domande di quiz a scelta multipla (parola giapponese, quattro significati "
        "in inglese A-D, lettera corretta). Con review=true usa le parole che l'utente "
        "ha sbagliato più spesso."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "n": {"type": "integer", "description": "Numero di domande, da 1 a 10"},
            "review": {"type": "boolean", "description": "true per ripassare le parole sbagliate"},
        },
        "required": ["n"],
    },
)

CHECK_ANSWER_DECL = types.FunctionDeclaration(
    name="check_answer",
    description=(
        "Corregge la risposta dell'utente a una domanda del quiz e la registra nei suoi "
        "progressi. Usala ogni volta che l'utente risponde con una lettera A-D."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "word": {"type": "string", "description": "la parola giapponese della domanda"},
            "letter": {"type": "string", "description": "la lettera scelta dall'utente, A-D"},
        },
        "required": ["word", "letter"],
    },
)

SHOW_PROGRESS_DECL = types.FunctionDeclaration(
    name="show_progress",
    description="Mostra i progressi dell'utente nei quiz: risposte, accuratezza, parole da ripassare.",
    parameters_json_schema={"type": "object", "properties": {}},
)

V1_DECLS = [LOOKUP_WORD_DECL, MAKE_QUIZ_V1_DECL, CHECK_ANSWER_DECL, SHOW_PROGRESS_DECL]
V1_REGISTRY = {
    "lookup_word": lookup_word,
    "make_quiz": make_quiz_v1, #il tool si chiama sempre make_quiz, è il registro a decidere quale funzione py esegue quel nome
    "check_answer": check_answer,
    "show_progress": show_progress,
}