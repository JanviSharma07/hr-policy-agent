import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from app.retrieval.search import search, to_citation
from app.agent.llm import generate_json
from app.agent.prompts import QA_SYSTEM, CALC_SYSTEM, REWRITE_SYSTEM, NOT_COVERED
from app.agent.router import classify
from app.agent.calculator import safe_eval, format_amount


class AgentState(TypedDict, total=False):
    question: str
    intent: str
    chunks: list[dict]
    answer: str
    used: list
    clarify: bool            # True when the agent asks the employee for a missing detail
    search_query: str        # rewritten question used for a second search
    retries: int
    citations: list[dict]
    trace: Annotated[list[str], operator.add]  # each node appends its own step


def _excerpt_prompt(state: AgentState) -> str:
    excerpts = "\n\n".join(
        f"[{i}] {c['metadata']['title']} (version {c['metadata']['version']}), "
        f"section {c['metadata']['section']}\n{c['text']}"
        for i, c in enumerate(state["chunks"], start=1)
    )
    return f"Policy excerpts:\n\n{excerpts}\n\nEmployee question: {state['question']}"


# ---------- Supervisor ----------

def supervisor(state: AgentState) -> dict:
    intent, source = classify(state["question"])
    return {"intent": intent, "trace": [f"Router ({source}): {intent}"]}


def after_supervisor(state: AgentState) -> str:
    return "not_covered" if state["intent"] == "out_of_scope" else "retrieve"


# ---------- Retrieval ----------

MAX_RETRIES = 1


def retrieve(state: AgentState) -> dict:
    query = state.get("search_query") or state["question"]
    chunks = search(query)
    return {"chunks": chunks, "trace": [f"Searched policies: {len(chunks)} relevant section(s) found"]}


def after_retrieve(state: AgentState) -> str:
    if not state["chunks"]:
        return "rewrite" if state.get("retries", 0) < MAX_RETRIES else "not_covered"
    return "calculator" if state["intent"] == "calculation" else "policy_qa"


def rewrite(state: AgentState) -> dict:
    out = generate_json(REWRITE_SYSTEM, state["question"])
    query = str(out.get("query", "")).strip() or state["question"]
    return {"search_query": query, "retries": state.get("retries", 0) + 1,
            "trace": [f'No match, so the question was rewritten: "{query}"']}


# ---------- Specialist agents ----------

def not_covered(state: AgentState) -> dict:
    return {"answer": NOT_COVERED, "citations": [], "trace": ["No matching policy found"]}


def policy_qa(state: AgentState) -> dict:
    out = generate_json(QA_SYSTEM, _excerpt_prompt(state))
    return {
        "answer": str(out.get("answer", "")).strip(),
        "used": out.get("sources", []),
        "trace": ["Policy Q&A agent wrote the answer"],
    }


def calculator(state: AgentState) -> dict:
    out = generate_json(CALC_SYSTEM, _excerpt_prompt(state))
    sources = out.get("sources", [])

    if str(out.get("missing", "")).strip():
        return {"answer": out["missing"].strip(), "used": sources, "clarify": True,
                "trace": ["Calculator agent: needs one more detail from you"]}

    lines, totals = [], {}
    for item in out.get("items", []):
        try:
            value = safe_eval(str(item["expression"]))
        except (KeyError, ValueError, SyntaxError, ZeroDivisionError):
            continue  # skip anything that isn't plain arithmetic
        unit = str(item.get("unit", "Rs.")).strip()
        lines.append(f"- {item.get('label', 'Amount')}: {format_amount(value, unit)}")
        totals[unit] = totals.get(unit, 0) + value

    if not lines:
        return {"answer": "", "used": [], "trace": ["Calculator agent: no usable rate found"]}

    answer = "\n".join(lines)
    if len(lines) > 1:
        answer += "\n\nTotal: " + " + ".join(format_amount(v, u) for u, v in totals.items())
    if str(out.get("note", "")).strip():
        answer += "\n\n" + out["note"].strip()
    return {"answer": answer, "used": sources,
            "trace": [f"Calculator agent: worked out {len(lines)} amount(s) in Python"]}


# ---------- Citation check ----------

def check_citations(state: AgentState) -> dict:
    n = len(state["chunks"])
    # keep only real excerpt numbers; drops anything the LLM made up
    used = sorted({i for i in state.get("used", []) if isinstance(i, int) and 1 <= i <= n})
    citations = [{**to_citation(state["chunks"][i - 1]), "text": state["chunks"][i - 1]["text"]} for i in used]

    if state.get("clarify"):  # a follow-up question doesn't need a source
        return {"citations": citations, "trace": ["Asked you for the missing detail"]}
    if not citations or not state.get("answer"):
        return {"answer": NOT_COVERED, "citations": [], "trace": ["Citation check failed: answer not backed by a policy"]}
    return {"citations": citations, "trace": [f"Citation check passed: {len(citations)} source(s)"]}


# ---------- Graph ----------

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("supervisor", supervisor)
    g.add_node("retrieve", retrieve)
    g.add_node("rewrite", rewrite)
    g.add_node("policy_qa", policy_qa)
    g.add_node("calculator", calculator)
    g.add_node("check_citations", check_citations)
    g.add_node("not_covered", not_covered)

    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", after_supervisor,
                            {"retrieve": "retrieve", "not_covered": "not_covered"})
    g.add_conditional_edges("retrieve", after_retrieve,
                            {"policy_qa": "policy_qa", "calculator": "calculator",
                             "rewrite": "rewrite", "not_covered": "not_covered"})
    g.add_edge("rewrite", "retrieve")
    g.add_edge("policy_qa", "check_citations")
    g.add_edge("calculator", "check_citations")
    g.add_edge("check_citations", END)
    g.add_edge("not_covered", END)
    return g.compile()


agent = build_graph()


def run_agent(question: str) -> dict:
    result = agent.invoke({"question": question, "trace": [], "retries": 0})
    return {
        "intent": result.get("intent"),
        "answer": result["answer"],
        "citations": result.get("citations", []),
        "trace": result["trace"],
    }