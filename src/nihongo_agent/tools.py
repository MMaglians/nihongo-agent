"""Tool dell'agente. Qui un dizionario toy scritto a mano"""

from google.genai import types

# Mini dizionario di prova (dati scritti a mano).
MINI_DICT = {
    "食べる": {"reading": "たべる", "meaning": "to eat", "pos": "verbo ichidan"},
    "飲む": {"reading": "のむ", "meaning": "to drink", "pos": "verbo godan"},
    "猫": {"reading": "ねこ", "meaning": "cat", "pos": "nome"},
    "水": {"reading": "みず", "meaning": "water", "pos": "nome"},
    "大きい": {"reading": "おおきい", "meaning": "big", "pos": "aggettivo in -i"},
}

def lookup_word(word: str) -> dict:
    """Cerca una parola nel dizionario. Non solleva mai eccezioni."""
    entry = MINI_DICT.get(word.strip())
    if entry is None:
        return {"found": False, "word": word}
    return {"found": True, "word": word, **entry}

# Dichiarazione per il modello: nome, descrizione, schema JSON dei parametri.
LOOKUP_WORD_DECL = types.FunctionDeclaration(
    name="lookup_word",
    description=(
        "Cerca una parola giapponese nel dizionario dell'utente e restituisce "
        "lettura in kana, significato e categoria grammaticale. "
        "Usala ogni volta che serve il significato di una parola giapponese."
    ),
    parameters_json_schema={
        "type": "object",
        "properties": {
            "word": {
                "type": "string",
                "description": "La parola in giapponese, es. 食べる",
            }
        },
        "required": ["word"],
    },
)

# Tabella di smistamento: nome del tool -> funzione Python vera.
# Rende esplicito quali tool esistono
TOOL_REGISTRY = {"lookup_word": lookup_word}

def execute_tool(name: str, args: dict) -> dict:
    """Esegue il tool richiesto dal modello, con controlli di sicurezza."""
    func = TOOL_REGISTRY.get(name)
    if func is None:
        return {"error": f"tool sconosciuto: {name}"}
    try:
        return func(**args)
    except TypeError as exc: # argomenti sbagliati inventati dal modello
        return {"error": f"argomenti non validi: {exc}"}