import operator
from typing import Annotated, TypedDict
from langgraph.graph import StateGraph, START, END
from app.retrieval.search import search, to_citation
from app.agent.llm import generate_json
from app.agent.prompts import QA_SYSTEM, NOT_COVERED


class AgentState(TypedDict, total=False):
    question: str
    chunks: list[dict]
    answer: str
    used: list
    citations: list[dict]
    trace: Annotated[list[str], operator.add]  # each node appends its own step


def retrieve(state: AgentState) -> dict:
    chunks = search(state["question"])
    return {"chunks": chunks, "trace": [f"Searched policies: {len(chunks)} relevant section(s) found"]}


def after_retrieve(state: AgentState) -> str:
    return "generate" if state["chunks"] else "not_covered"


def not_covered(state: AgentState) -> dict:
    return {"answer": NOT_COVERED, "citations": [], "trace": ["No matching policy found"]}


def generate(state: AgentState) -> dict:
    excerpts = "\n\n".join(
        f"[{i}] {c['metadata']['title']} (version {c['metadata']['version']}), "
        f"section {c['metadata']['section']}\n{c['text']}"
        for i, c in enumerate(state["chunks"], start=1)
    )
    prompt = f"Policy excerpts:\n\n{excerpts}\n\nEmployee question: {state['question']}"
    out = generate_json(QA_SYSTEM, prompt)
    return {
        "answer": str(out.get("answer", "")).strip(),
        "used": out.get("sources", []),
        "trace": ["Wrote answer from the policy sections"],
    }


def check_citations(state: AgentState) -> dict:
    n = len(state["chunks"])
    # keep only real excerpt numbers; drops anything the LLM made up
    used = sorted({i for i in state.get("used", []) if isinstance(i, int) and 1 <= i <= n})
    if not used or not state.get("answer"):
        return {"answer": NOT_COVERED, "citations": [], "trace": ["Citation check failed: answer not backed by a policy"]}
    citations = [{**to_citation(state["chunks"][i - 1]), "text": state["chunks"][i - 1]["text"]} for i in used]
    return {"citations": citations, "trace": [f"Citation check passed: {len(citations)} source(s)"]}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("retrieve", retrieve)
    g.add_node("generate", generate)
    g.add_node("check_citations", check_citations)
    g.add_node("not_covered", not_covered)

    g.add_edge(START, "retrieve")
    g.add_conditional_edges("retrieve", after_retrieve, {"generate": "generate", "not_covered": "not_covered"})
    g.add_edge("generate", "check_citations")
    g.add_edge("check_citations", END)
    g.add_edge("not_covered", END)
    return g.compile()


agent = build_graph()


def run_agent(question: str) -> dict:
    result = agent.invoke({"question": question, "trace": []})
    return {
        "answer": result["answer"],
        "citations": result.get("citations", []),
        "trace": result["trace"],
    }