"""Pilastro v1: l'agente della v0 come grafo LangGraph, con router e memoria per conversazione."""
import operator
import time
from typing import Annotated, Literal, TypedDict

from google.genai import types
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ValidationError

from nihongo_agent.agent import SYSTEM_PROMPT, _usage, make_config
from nihongo_agent.retry import generate_with_retry
from nihongo_agent.tools import execute_tool
from nihongo_agent.tracing import TraceLog

MAX_STEPS = 6  # come la v0 (DECISIONS.md, punto 4)

ROUTER_PROMPT = (
    "Classifica il messaggio di uno studente di giapponese in UNA categoria.\n"
    "- usa_tool: chiede significato o lettura di una parola giapponese, oppure un quiz "
    "o la risposta a una domanda del quiz;\n"
    "- recupera: chiede qualcosa che ha studiato o scritto nei suoi appunti "
    "(lezioni, grammatica vista, esempi presi a lezione);\n"
    "- rispondi: saluti, domande generali, conversazione, tutto il resto.\n"
    "Messaggio: "
)

NO_TOOL_PROMPT = SYSTEM_PROMPT + (
    " In questo turno non hai accesso al dizionario: se ti chiedono il significato "
    "o la lettura di una parola, di' che non puoi verificarla e invita a chiederla di nuovo."
)

class Route(BaseModel):
    route: Literal["usa_tool", "recupera", "rispondi"] #Forma di typing speciale per definire literal types (a.k.a. value types).
    
class State(TypedDict):
    messages: Annotated[list[dict], operator.add] #cronologia: i nuovi mex si accodano
    route: str      #sovrascritto a ogni turno
    steps: int      #chiamate al modello nel loop dei tool, in questo turno
    context: str    #testo recuperato in questo turno: NON entra nella cronologia
    
# --- conversione tra oggetti Gemini e dizionari (lo stato salvato deve essere serializzabile)
def to_dict(content: types.Content) -> dict:
    return content.model_dump(mode="json", exclude_none=True)

def to_content(message: dict) -> types.Content:
    return types.Content.model_validate(message)

def user_message(text: str) -> dict:
    return {"role": "user", "parts": [{"text": text}]}


def model_message(text: str) -> dict:
    return {"role": "model", "parts": [{"text": text}]}


def text_of(message: dict) -> str:
    return "".join(p.get("text", "") for p in message.get("parts", []) if not p.get("thought"))


def calls_of(message: dict) -> list[dict]:
    return [p["function_call"] for p in message.get("parts", []) if "function_call" in p]


def last_user_text(messages: list[dict]) -> str:
    for m in reversed(messages):
        if m["role"] == "user" and text_of(m):
            return text_of(m)
    return ""

def build_graph(client, model: str, *, trace: TraceLog | None = None,
                checkpointer=None, max_steps: int = MAX_STEPS):
    trace = trace or TraceLog()

    def call_model(contents, config, node: str):
        started = time.perf_counter()
        response = generate_with_retry(client, model=model, contents=contents, config=config)
        trace.event("model", node=node, seconds=round(time.perf_counter() - started, 2),
                    **_usage(response))
        return response

    def router(state: State):
        """
        classifica la domanda, legge la risposta e scrive nello stato 
        quale ramo seguire
        """
        question = last_user_text(state["messages"])
        trace.event("user", text=question)
        config = types.GenerateContentConfig(
            response_mime_type="application/json", response_schema=Route, temperature=0
        )
        response = call_model(ROUTER_PROMPT + question, config, "router")
        try:
            route = Route.model_validate_json(response.text or "").route
        except ValidationError:
            route = "usa_tool"  # nel dubbio, il ramo che può verificare sul dizionario
            trace.event("error", text="router: risposta non valida, uso usa_tool")
        trace.event("route", route=route)
        return {"route": route, "steps": 0, "context": ""}

    def retrieve(state: State):
        # Segnaposto: nel Giorno B qui arriva il retrieval sui tuoi appunti.
        return {"context": "Nessun appunto indicizzato per ora."}

    def answer(state: State):
        messages = state["messages"]
        if state["context"]:
            note = user_message(f"Contesto dagli appunti:\n{state['context']}")
            messages = messages[:-1] + [note, messages[-1]]
        config = types.GenerateContentConfig(system_instruction=NO_TOOL_PROMPT, temperature=0)
        response = call_model([to_content(m) for m in messages], config, "answer")
        if not response.candidates or response.candidates[0].content is None:
            trace.event("error", text="risposta vuota (blocco di sicurezza?)")
            return {"messages": [model_message("Il modello non ha prodotto una risposta. Riprova.")]}
        trace.event("final", text=response.text or "")
        return {"messages": [to_dict(response.candidates[0].content)]}
    
    def agent(state: State):
        step = state["steps"] + 1
        response = call_model([to_content(m) for m in state["messages"]], make_config(), "agent")
        if not response.candidates or response.candidates[0].content is None:
            trace.event("error", step=step, text="risposta vuota (blocco di sicurezza?)")
            return {"messages": [model_message("Il modello non ha prodotto una risposta. Riprova.")],
                    "steps": step}
        if not response.function_calls:
            trace.event("final", step=step, text=response.text or "")
        return {"messages": [to_dict(response.candidates[0].content)], "steps": step}
    
    def run_tools(state: State):
        parts = []
        for call in calls_of(state["messages"][-1]):
            args = dict(call.get("args") or {})
            result = execute_tool(call["name"], args)
            trace.event("tool", step=state["steps"], name=call["name"], args=args, result=result)
            part = types.Part.from_function_response(name=call["name"], response=result)
            parts.append(part.model_dump(mode="json", exclude_none=True))
        return {"messages": [{"role": "user", "parts": parts}]}
    
    def limit(state: State):
        trace.event("limit", max_steps=max_steps)
        return {"messages": [model_message(f"Mi fermo: ho raggiunto il limite di {max_steps} passi.")]}

    def after_agent(state: State) -> str:
        return "run_tools" if calls_of(state["messages"][-1]) else "end"

    def after_tools(state: State) -> str:
        return "limit" if state["steps"] >= max_steps else "agent"
    
    """
    Stesso loop di v0: 
    - for step in range(...) = edge run_tools -> agent
    - return senza tool = edge after agent -> END
    - limite passi = edge after_tools -> limit 
    """
    graph = StateGraph(State)
    graph.add_node("router", router)
    graph.add_node("retrieve", retrieve)
    graph.add_node("answer", answer)
    graph.add_node("agent", agent)
    graph.add_node("run_tools", run_tools)
    graph.add_node("limit", limit)
    
    graph.add_edge(START, "router")
    graph.add_conditional_edges("router", lambda s: s["route"],
                                {"usa_tool": "agent", "recupera": "retrieve", "rispondi": "answer"})
    graph.add_edge("retrieve", "answer")
    graph.add_edge("answer", END)
    graph.add_conditional_edges("agent", after_agent, {"run_tools": "run_tools", "end": END})
    graph.add_conditional_edges("run_tools", after_tools, {"agent": "agent", "limit": "limit"})
    graph.add_edge("limit", END)
    return graph.compile(checkpointer=checkpointer)
    
def run_turn_v1(graph, thread_id: str, user_text: str) -> str:
    """Un turno della conversazione `thread_id`: stessa firma logica di run_turn della v0."""
    config = {"configurable": {"thread_id": thread_id}}
    state = graph.invoke({"messages": [user_message(user_text)]}, config)
    return text_of(state["messages"][-1])
    
    
    
    
    
