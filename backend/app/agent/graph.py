import operator
from datetime import date
from typing import Annotated, Iterator, TypedDict
from langgraph.graph import StateGraph, START, END
from app.retrieval.search import search, to_citation
from app.retrieval.vector_store import get_family_chunks
from app.agent.llm import generate_json
from app.agent.prompts import (
    QA_SYSTEM, CALC_SYSTEM, REWRITE_SYSTEM, MEMORY_SYSTEM, ELIGIBILITY_SYSTEM,
    COMPARE_SYSTEM, SUMMARY_SYSTEM, NOT_COVERED,
)
from app.agent.router import classify
from app.agent.calculator import safe_eval, format_amount

MAX_RETRIES = 1        # how many times the agent may rewrite a failed search
HISTORY_MESSAGES = 6   # how much of the chat the memory agent reads


class AgentState(TypedDict, total=False):
    question: str            # what the employee typed
    history: list[dict]      # earlier messages in this chat
    profile: dict            # join_date, grade, city of the logged-in employee
    standalone: str          # question after the memory agent resolved follow-ups
    intent: str
    chunks: list[dict]
    answer: str
    used: list
    clarify: bool            # True when the agent asks the employee for a missing detail
    search_query: str        # rewritten question used for a second search
    retries: int
    citations: list[dict]
    trace: Annotated[list[str], operator.add]  # each node appends its own step


# ---------- Helpers ----------

def _q(state: AgentState) -> str:
    return state.get("standalone") or state["question"]


def months_of_service(join_date: date, today: date | None = None) -> int:
    today = today or date.today()
    months = (today.year - join_date.year) * 12 + (today.month - join_date.month)
    if today.day < join_date.day:
        months -= 1
    return max(months, 0)


def _profile_text(profile: dict | None) -> str:
    profile = profile or {}
    parts = []
    if profile.get("join_date"):
        jd = profile["join_date"]
        jd = jd if isinstance(jd, date) else date.fromisoformat(str(jd))
        parts.append(f"joined on {jd.isoformat()}, which is {months_of_service(jd)} full months "
                     f"of service as of {date.today().isoformat()}")
    if profile.get("grade"):
        parts.append(f"grade {profile['grade']}")
    if profile.get("city"):
        parts.append(f"based in {profile['city']}")
    return "Employee profile: " + ("; ".join(parts) if parts else "not provided") + "."


def _excerpt_prompt(state: AgentState, with_profile: bool = False) -> str:
    excerpts = "\n\n".join(
        f"[{i}] {c['metadata']['title']} (version {c['metadata']['version']}, "
        f"{'current' if c['metadata'].get('is_active', True) else 'archived'}), "
        f"section {c['metadata']['section']}\n{c['text']}"
        for i, c in enumerate(state["chunks"], start=1)
    )
    profile = f"{_profile_text(state.get('profile'))}\n\n" if with_profile else ""
    return f"Policy excerpts:\n\n{excerpts}\n\n{profile}Employee question: {_q(state)}"


# ---------- Memory ----------

def memory(state: AgentState) -> dict:
    history = state.get("history") or []
    if not history:
        return {"standalone": state["question"]}
    convo = "\n".join(f"{m['sender']}: {m['content']}" for m in history[-HISTORY_MESSAGES:])
    out = generate_json(MEMORY_SYSTEM, f"Conversation so far:\n{convo}\n\nLatest message: {state['question']}")
    standalone = str(out.get("question", "")).strip() or state["question"]
    if standalone.strip().lower() == state["question"].strip().lower():
        return {"standalone": state["question"]}
    return {"standalone": standalone, "trace": [f'Memory: understood this as "{standalone}"']}


# ---------- Supervisor ----------

def supervisor(state: AgentState) -> dict:
    intent, source = classify(_q(state))
    return {"intent": intent, "trace": [f"Router ({source}): {intent}"]}


def after_supervisor(state: AgentState) -> str:
    return "not_covered" if state["intent"] == "out_of_scope" else "retrieve"


# ---------- Retrieval ----------

def retrieve(state: AgentState) -> dict:
    query = state.get("search_query") or _q(state)
    intent = state["intent"]

    if intent in ("compare", "summarize"):
        # Find which policy the question is about, then read that whole policy
        hits = search(query, include_archived=(intent == "compare"))
        if not hits:
            return {"chunks": [], "trace": ["Searched policies: 0 relevant section(s) found"]}
        top = hits[0]["metadata"]
        family = top.get("family_id", top["document_id"])
        chunks = get_family_chunks(family, active_only=(intent == "summarize"))
        versions = sorted({c["metadata"]["version"] for c in chunks})
        return {"chunks": chunks,
                "trace": [f"Found policy \"{top['title']}\": read {len(chunks)} section(s) "
                          f"across version(s) {', '.join(versions)}"]}

    chunks = search(query)
    return {"chunks": chunks, "trace": [f"Searched policies: {len(chunks)} relevant section(s) found"]}


AGENT_FOR_INTENT = {
    "calculation": "calculator",
    "eligibility": "eligibility",
    "compare": "comparison",
    "summarize": "summarizer",
}


def after_retrieve(state: AgentState) -> str:
    if not state["chunks"]:
        return "rewrite" if state.get("retries", 0) < MAX_RETRIES else "not_covered"
    return AGENT_FOR_INTENT.get(state["intent"], "policy_qa")


def rewrite(state: AgentState) -> dict:
    out = generate_json(REWRITE_SYSTEM, _q(state))
    query = str(out.get("query", "")).strip() or _q(state)
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
    out = generate_json(CALC_SYSTEM, _excerpt_prompt(state, with_profile=True))
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


def eligibility(state: AgentState) -> dict:
    out = generate_json(ELIGIBILITY_SYSTEM, _excerpt_prompt(state, with_profile=True))
    verdict = str(out.get("verdict", "")).strip()
    result = {"answer": str(out.get("answer", "")).strip(), "used": out.get("sources", []),
              "trace": [f"Eligibility agent checked your profile: {verdict or 'no verdict'}"]}
    if verdict == "need_info":
        result["clarify"] = True
    return result


def comparison(state: AgentState) -> dict:
    versions = {c["metadata"]["version"] for c in state["chunks"]}
    if len(versions) < 2:
        title = state["chunks"][0]["metadata"]["title"]
        return {"answer": f"Only one version of the {title} is on file (version {next(iter(versions))}), "
                          f"so there is nothing to compare yet.",
                "used": [1], "trace": ["Comparison agent: only one version exists"]}
    out = generate_json(COMPARE_SYSTEM, _excerpt_prompt(state))
    return {"answer": str(out.get("answer", "")).strip(), "used": out.get("sources", []),
            "trace": [f"Comparison agent compared versions {', '.join(sorted(versions))}"]}


def summarizer(state: AgentState) -> dict:
    out = generate_json(SUMMARY_SYSTEM, _excerpt_prompt(state))
    return {"answer": str(out.get("answer", "")).strip(), "used": out.get("sources", []),
            "trace": ["Summarizer agent summarised the policy"]}


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

SPECIALISTS = {
    "policy_qa": policy_qa,
    "calculator": calculator,
    "eligibility": eligibility,
    "comparison": comparison,
    "summarizer": summarizer,
}


def build_graph():
    g = StateGraph(AgentState)
    g.add_node("memory", memory)
    g.add_node("supervisor", supervisor)
    g.add_node("retrieve", retrieve)
    g.add_node("rewrite", rewrite)
    for name, fn in SPECIALISTS.items():
        g.add_node(name, fn)
    g.add_node("check_citations", check_citations)
    g.add_node("not_covered", not_covered)

    g.add_edge(START, "memory")
    g.add_edge("memory", "supervisor")
    g.add_conditional_edges("supervisor", after_supervisor,
                            {"retrieve": "retrieve", "not_covered": "not_covered"})
    g.add_conditional_edges("retrieve", after_retrieve,
                            {**{name: name for name in SPECIALISTS},
                             "rewrite": "rewrite", "not_covered": "not_covered"})
    g.add_edge("rewrite", "retrieve")
    for name in SPECIALISTS:
        g.add_edge(name, "check_citations")
    g.add_edge("check_citations", END)
    g.add_edge("not_covered", END)
    return g.compile()


agent = build_graph()


def _initial_state(question: str, profile: dict | None, history: list[dict] | None) -> dict:
    return {"question": question, "profile": profile or {}, "history": history or [],
            "trace": [], "retries": 0}


def _result(state: dict) -> dict:
    return {
        "intent": state.get("intent"),
        "answer": state["answer"],
        "citations": state.get("citations", []),
        "trace": state["trace"],
    }


def run_agent(question: str, profile: dict | None = None, history: list[dict] | None = None) -> dict:
    return _result(agent.invoke(_initial_state(question, profile, history)))


def stream_agent(question: str, profile: dict | None = None,
                 history: list[dict] | None = None) -> Iterator[tuple[str, object]]:
    """Yields ("step", text) as each agent finishes, then ("done", result)."""
    seen, final = 0, None
    for state in agent.stream(_initial_state(question, profile, history), stream_mode="values"):
        trace = state.get("trace", [])
        for line in trace[seen:]:
            yield "step", line
        seen = len(trace)
        final = state
    yield "done", _result(final)
