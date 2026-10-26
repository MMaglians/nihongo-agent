"""Un solo giro di function calling, fatto a mano (senza automatismi)."""
from google.genai import types

from nihongo_agent.tools import LOOKUP_WORD_DECL, execute_tool

SYSTEM_PROMPT = (
    "Sei un tutor di giapponese per uno studente italiano. "
    "Per il significato delle parole usa sempre il tool lookup_word, "
    "non la tua memoria. Rispondi in italiano, in modo breve."
)


def make_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=[LOOKUP_WORD_DECL])],
        # Spegniamo l'automatismo dell'SDK: il ciclo lo scriviamo noi.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0,
    )


def ask_once(client, model: str, question: str) -> tuple[str, list[str]]:
    """Domanda -> (eventuale tool) -> risposta finale. Restituisce testo e traccia."""
    trace: list[str] = []
    config = make_config()
    history = [types.Content(role="user", parts=[types.Part(text=question)])]

    # Chiamata 1: il modello decide se rispondere o chiedere un tool.
    response = client.models.generate_content(model=model, contents=history, config=config)
    calls = response.function_calls or []
    if not calls:
        trace.append("modello: risponde senza tool")
        return response.text or "", trace

    # Il turno del modello va in memoria così com'è (contiene le thought signature).
    history.append(response.candidates[0].content)

    result_parts = []
    for call in calls:
        args = dict(call.args or {})
        trace.append(f"azione: {call.name}({args})")
        result = execute_tool(call.name, args)
        trace.append(f"osservazione: {result}")
        result_parts.append(types.Part.from_function_response(name=call.name, response=result))
    history.append(types.Content(role="user", parts=result_parts))

    # Chiamata 2: il modello legge l'osservazione e scrive la risposta.
    final = client.models.generate_content(model=model, contents=history, config=config)
    trace.append("modello: risposta finale")
    return final.text or "", trace