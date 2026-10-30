"""Il loop dell'agente: il modello sceglie, il codice esegue, il risultato rientra."""
import time

from google.genai import types

from nihongo_agent.retry import generate_with_retry
from nihongo_agent.tools import ALL_DECLS, execute_tool
from nihongo_agent.tracing import TraceLog

SYSTEM_PROMPT = (
    "Sei un tutor di giapponese per uno studente italiano. Rispondi in italiano, "
    "in modo breve. Per il significato o la lettura di una parola usa sempre "
    "lookup_word, non la tua memoria. Se la parola non è nel dizionario, dillo: "
    "se aggiungi qualcosa dalla tua conoscenza generale, specifica che non viene "
    "dal dizionario. Per un quiz chiama make_quiz una volta, poi proponi UNA "
    "domanda alla volta con le opzioni A-D, senza rivelare la risposta. Dopo la "
    "risposta dell'utente di' se è corretta e mostra la lettura in kana."
)

def make_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=[types.Tool(function_declarations=ALL_DECLS)],
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        temperature=0,
    )

def _usage(response) -> dict:
    meta = response.usage_metadata
    if meta is None:
        return {}
    return {
        "input_tokens": meta.prompt_token_count,
        "output_tokens": meta.candidates_token_count,
        "thinking_tokens": meta.thoughts_token_count,  # fatturati come output
    }
def _close(history: list, text: str) -> str:
    """Chiude il turno con un messaggio del modello, così i ruoli restano alternati."""
    history.append(types.Content(role="model", parts=[types.Part(text=text)]))
    return text

def run_turn(client, model: str, history: list, user_text: str, *,
             max_steps: int = 6, trace: TraceLog | None = None) -> str:
    """Un turno: gira finché il modello risponde senza tool, o finiscono i passi."""
    trace = trace or TraceLog()
    config = make_config()
    history.append(types.Content(role="user", parts=[types.Part(text=user_text)]))
    trace.event("user", text=user_text)

    for step in range(1, max_steps + 1):
        started = time.perf_counter()
        response = generate_with_retry(client, model=model, contents=history, config=config)
        trace.event("model", step=step, seconds=round(time.perf_counter() - started, 2),
                    **_usage(response))

        if not response.candidates or response.candidates[0].content is None:
            trace.event("error", step=step, text="risposta vuota (blocco di sicurezza?)")
            return _close(history, "Il modello non ha prodotto una risposta. Riprova.")

        history.append(response.candidates[0].content)  # il turno del modello, intatto
        calls = response.function_calls or []
        if not calls:
            answer = response.text or ""
            trace.event("final", step=step, text=answer)
            return answer

        parts = []
        for call in calls:
            args = dict(call.args or {})
            result = execute_tool(call.name, args)
            trace.event("tool", step=step, name=call.name, args=args, result=result)
            parts.append(types.Part.from_function_response(name=call.name, response=result))
        history.append(types.Content(role="user", parts=parts))

    trace.event("limit", max_steps=max_steps)
    return _close(history, f"Mi fermo: ho raggiunto il limite di {max_steps} passi.")