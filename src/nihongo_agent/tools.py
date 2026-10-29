"""Tool dell'agente: dizionario JMdict e quiz."""
from google.genai import types

from nihongo_agent.dictionary import Dictionary

_dictionary: Dictionary | None = None


def get_dictionary() -> Dictionary:
    """Carica il dizionario la prima volta che serve (poi resta in memoria)."""
    global _dictionary
    if _dictionary is None:
        _dictionary = Dictionary.from_file()
    return _dictionary


def set_dictionary(dictionary: Dictionary | None) -> None:
    """Serve ai test: permette di usare un dizionario finto."""
    global _dictionary #global permette a una fct di modificare la variabile _dictionary nel modulo
    _dictionary = dictionary

def lookup_word(word: str) -> dict:
    """Cerca una parola (kanji o kana) nel dizionario."""
    entries = get_dictionary().lookup(word)
    if not entries:
        return{"found": False, "word": word}
    return{"found": True, "word": word, "entries": entries}

def make_quiz(n: int=3) -> dict:
     """Genera n domande a scelta multipla (da 1 a 10)."""
     n = max(1, min(int(n), 10)) # il modello può mandare 3.0 o un numero enorme
     return {"questions": get_dictionary().quiz(n)}
 

LOOKUP_WORD_DECL = types.FunctionDeclaration(
     name = "lookup_word",
     description=(
        "Cerca una parola giapponese (in kanji o in kana) nel dizionario JMdict "
        "e restituisce letture, significati in inglese e categoria grammaticale. "
        "Contiene solo le parole comuni. Usala ogni volta che serve il significato "
        "di una parola giapponese."
     ),
     parameters_json_schema={
         "type": "object",
         "properties": {
             "word": {"type": "string", "description": "la parola in giapponese, es. 食べる"}
         },
         "required": ["word"],
     },
 )
 
 
MAKE_QUIZ_DECL = types.FunctionDeclaration(
    name="make_quiz",
    description=(
        "Genera domande di quiz a scelta multipla (parola giapponese, quattro "
        "significati in inglese A-D, lettera corretta). Usala quando l'utente "
        "chiede un quiz o un ripasso del vocabolario."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "n": {"type": "integer", "description": "Numero di domande, da 1 a 10"}
        },
        "required": ["n"],
    },
)

ALL_DECLS = [LOOKUP_WORD_DECL, MAKE_QUIZ_DECL]
TOOL_REGISTRY = {"lookup_word": lookup_word, "make_quiz": make_quiz}

def execute_tool(name: str, args: dict) -> dict:
    """Esegue il tool richiesto dal modello. Gli errori diventano osservazioni."""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": f"tool sconosciuto: {name}"}
    try:
        return func(**args)
    except TypeError as exc:  # argomenti inventati dal modello
        return {"error": f"argomenti non validi: {exc}"}
    except Exception as exc:  # il loop non deve morire per un tool
        return {"error": f"errore del tool {name}: {type(exc).__name__}: {exc}"}