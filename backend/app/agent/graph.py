import operator
import re
from datetime import date
from typing import Annotated, Iterator, TypedDict
from langgraph.graph import StateGraph, START, END
from app.config import AGENT_RELATIVE_KEEP, OUT_OF_SCOPE_OVERRIDE
from app.retrieval.search import search, to_citation
from app.retrieval.vector_store import get_family_chunks
from app.agent.llm import generate_json
from app.agent.prompts import (
    QA_SYSTEM, CALC_SYSTEM, ELIGIBILITY_SYSTEM,
    COMPARE_SYSTEM, SUMMARY_SYSTEM, NOT_COVERED,
)
from app.agent.router import classify
from app.agent.calculator import safe_eval, format_amount, is_money, show_working

HISTORY_MESSAGES = 6   # how many earlier chat messages the agents get
FOLLOW_UP = re.compile(r"^(and|also|what about|how about|yes|no|yeah|yep|nope|ok|okay|then|but|so|same)\b"
                       r"|\b(it|that|this|those|these|they|them|there|same)\b", re.I)


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
    history = state.get("history") or []
    chat = ""
    if history:  # so an answer to an earlier clarifying question isn't lost
        lines = "\n".join(f"{m['sender']}: {m['content']}" for m in history[-4:])
        chat = f"Earlier in this chat (use it for details the employee already gave):\n{lines}\n\n"
    return f"Policy excerpts:\n\n{excerpts}\n\n{profile}{chat}Employee question: {state['question']}"


# ---------- Memory ----------

def memory(state: AgentState) -> dict:
    """Short follow-ups ("what about two-wheelers?", "yes") are searched together with the
    previous question. No AI call here: the answering agent reads the chat history itself."""
    question = state["question"].strip()
    history = state.get("history") or []
    previous = next((m["content"] for m in reversed(history) if m["sender"] == "user"), None)
    if previous and len(question.split()) <= 10 and FOLLOW_UP.search(question):
        return {"standalone": f"{previous} {question}",
                "trace": [f'Memory: follow-up to "{previous[:80]}"']}
    return {"standalone": question}


# ---------- Supervisor ----------

def supervisor(state: AgentState) -> dict:
    intent, source = classify(_q(state))
    return {"intent": intent, "trace": [f"Router ({source}): {intent}"]}


def after_supervisor(state: AgentState) -> str:
    return "retrieve"  # even "out_of_scope" is checked against the policies before refusing


# ---------- Retrieval ----------

def retrieve(state: AgentState) -> dict:
    query = state.get("search_query") or _q(state)
    intent = state["intent"]

    if intent in ("compare", "summarize"):
        # Find which policy the question is about, then read that whole policy
        hits = search(query, include_archived=(intent == "compare")) or \
            search(query, include_archived=(intent == "compare"), min_relevance=0)[:1]
        if not hits:
            return {"chunks": [], "trace": ["Searched policies: 0 relevant section(s) found"]}
        top = hits[0]["metadata"]
        family = top.get("family_id", top["document_id"])
        chunks = get_family_chunks(family, active_only=(intent == "summarize"))
        versions = sorted({c["metadata"]["version"] for c in chunks})
        return {"chunks": chunks,
                "trace": [f"Found policy \"{top['title']}\": read {len(chunks)} section(s) "
                          f"across version(s) {', '.join(versions)}"]}

    chunks = search(query, relative_keep=AGENT_RELATIVE_KEEP)  # related sections too, for complete answers
    if chunks or intent == "out_of_scope":
        return {"chunks": chunks, "trace": [f"Searched policies: {len(chunks)} relevant section(s) found"]}
    # No strong match (common for long, personal questions): give the agent the closest
    # sections anyway and let it decide. Faster and more accurate than rewriting the question.
    chunks = search(query, min_relevance=0)
    return {"chunks": chunks,
            "trace": [f"No strong match, so the agent read the {len(chunks)} closest section(s)"]}


AGENT_FOR_INTENT = {
    "calculation": "calculator",
    "eligibility": "eligibility",
    "compare": "comparison",
    "summarize": "summarizer",
}


def after_retrieve(state: AgentState) -> str:
    if state["intent"] == "out_of_scope":
        best = max((c.get("relevance", 0) for c in state["chunks"]), default=0)
        return "override" if best >= OUT_OF_SCOPE_OVERRIDE else "not_covered"
    if not state["chunks"]:
        return "not_covered"
    return AGENT_FOR_INTENT.get(state["intent"], "policy_qa")


def override(state: AgentState) -> dict:
    """The router said off-topic, but a policy clearly matches: trust the evidence."""
    return {"intent": "policy_qa",
            "trace": ["Router said off-topic, but a policy section matches strongly, so answering anyway"]}


# ---------- Specialist agents ----------

def not_covered(state: AgentState) -> dict:
    return {"answer": NOT_COVERED, "citations": [], "trace": ["No matching policy found"]}


def policy_qa(state: AgentState) -> dict:
    out = generate_json(QA_SYSTEM, _excerpt_prompt(state), label="policy_qa")
    return {
        "answer": str(out.get("answer", "")).strip(),
        "used": out.get("sources", []),
        "trace": ["Policy Q&A agent wrote the answer"],
    }


def _asked_last_turn(state: AgentState) -> bool:
    """True if our previous message was a clarifying question (so this message is the reply)."""
    history = state.get("history") or []
    return bool(history) and history[-1]["sender"] == "assistant" and history[-1]["content"].rstrip().endswith("?")


def _hand_to_qa(state: AgentState, reason: str) -> dict:
    """A specialist couldn't answer (e.g. the calculator had nothing to compute):
    let the general Q&A agent answer from the same policy sections instead of refusing."""
    result = policy_qa(state)
    result["trace"] = [reason, "Handed the question to the Policy Q&A agent"] + result["trace"]
    return result


def calculator(state: AgentState) -> dict:
    out = generate_json(CALC_SYSTEM, _excerpt_prompt(state, with_profile=True), label="calculator")
    sources = out.get("sources", [])

    if str(out.get("missing", "")).strip():
        if _asked_last_turn(state):  # never ask twice in a row: answer with what we have
            return _hand_to_qa(state, "Calculator agent: still missing a detail after asking once")
        return {"answer": out["missing"].strip(), "used": sources, "clarify": True,
                "trace": ["Calculator agent: needs one more detail from you"]}

    lines, totals, money_lines = [], {}, 0
    for item in out.get("items", []):
        try:
            expression = str(item["expression"])
            value = safe_eval(expression)
        except (KeyError, ValueError, SyntaxError, ZeroDivisionError):
            continue  # skip anything that isn't plain arithmetic
        unit = str(item.get("unit", "Rs.")).strip()
        label = item.get("label", "Amount")
        shown = format_amount(value, unit)
        if re.search(r"[\d)]\s*[-+*/]", expression):  # it has real arithmetic, not just "-1"
            lines.append(f"- {label}: {show_working(expression)} = {shown}")  # show the maths
        else:
            lines.append(f"- {label}: {shown}")
        if is_money(unit):  # adding up days or counts would be meaningless
            totals[unit] = totals.get(unit, 0) + value
            money_lines += 1

    if not lines:
        return _hand_to_qa(state, "Calculator agent: nothing to calculate for this question")

    answer = "\n".join(lines)
    if money_lines > 1:
        answer += "\n\nTotal: " + " + ".join(format_amount(v, u) for u, v in totals.items())
    if str(out.get("note", "")).strip():
        answer += "\n\n" + out["note"].strip()
    return {"answer": answer, "used": sources,
            "trace": [f"Calculator agent: worked out {len(lines)} amount(s) in Python"]}


def eligibility(state: AgentState) -> dict:
    out = generate_json(ELIGIBILITY_SYSTEM, _excerpt_prompt(state, with_profile=True), label="eligibility")
    verdict = str(out.get("verdict", "")).strip()
    answer = str(out.get("answer", "")).strip()
    if verdict != "need_info" and (not answer or not out.get("sources")
                                   or answer.lower().startswith("this isn't covered")):
        return _hand_to_qa(state, "Eligibility agent: no eligibility rule found for this question")
    result = {"answer": answer, "used": out.get("sources", []),
              "trace": [f"Eligibility agent checked your profile: {verdict or 'no verdict'}"]}
    if verdict == "need_info":
        if _asked_last_turn(state):  # never ask twice in a row: answer with what we have
            return _hand_to_qa(state, "Eligibility agent: still missing a detail after asking once")
        result["clarify"] = True
    return result


def comparison(state: AgentState) -> dict:
    versions = {c["metadata"]["version"] for c in state["chunks"]}
    if len(versions) < 2:
        title = state["chunks"][0]["metadata"]["title"]
        return {"answer": f"Only one version of the {title} is on file (version {next(iter(versions))}), "
                          f"so there is nothing to compare yet.",
                "used": [1], "trace": ["Comparison agent: only one version exists"]}
    out = generate_json(COMPARE_SYSTEM, _excerpt_prompt(state), label="comparison")
    return {"answer": str(out.get("answer", "")).strip(), "used": out.get("sources", []),
            "trace": [f"Comparison agent compared versions {', '.join(sorted(versions))}"]}


def summarizer(state: AgentState) -> dict:
    out = generate_json(SUMMARY_SYSTEM, _excerpt_prompt(state), label="summarizer")
    return {"answer": str(out.get("answer", "")).strip(), "used": out.get("sources", []),
            "trace": ["Summarizer agent summarised the policy"]}


# ---------- Citation check ----------

_MARKERS = re.compile(r"(?:\s*\b(?:under|per|see|in|from|according to)\s+)?\s*\[\d+(?:\s*,\s*\d+)*\](?:\s*(?:,|and)\s*\[\d+(?:\s*,\s*\d+)*\])*", re.I)


def clean_answer(text: str) -> str:
    """Remove '[1]' style excerpt numbers: the sources are shown separately."""
    text = re.sub(r"\b(?:[Ss]ection|[Ee]xcerpt|[Ss]ource)s?\s+\[\d+(?:\s*,\s*\d+)*\]", "the policy", text)  # "Section [1] says"
    text = re.sub(r"(?:(?<=^)|(?<=[.:;!?]\s)|(?<=\n))\s*(?:[Uu]nder|[Pp]er|[Aa]s per|[Aa]ccording to)\s+\[\d+(?:\s*,\s*\d+)*\],?\s*", "", text)
    text = _MARKERS.sub("", text)
    text = re.sub(r"\s+([,.;:])", r"\1", text)
    text = re.sub(r",(?:\s*,)+", ",", text)
    text = re.sub(r"([.:;!?]),", r"\1", text)  # "portal., hotel" / "depends:, hotels"
    text = re.sub(r"(^|\n)(\s*-\s*)?,\s*", lambda m: m.group(1) + ("- " if m.group(2) else ""), text)  # "-, DA" -> "- DA"
    text = re.sub(r"[ \t]{2,}", " ", text).strip()
    return re.sub(r"(^-?\s*|[.!?]\s+|\n-?\s*)([a-z])", lambda m: m.group(1) + m.group(2).upper(), text)  # sentence starts


def check_citations(state: AgentState) -> dict:
    n = len(state["chunks"])
    # keep only real excerpt numbers; drops anything the LLM made up
    used = sorted({i for i in state.get("used", []) if isinstance(i, int) and 1 <= i <= n})
    citations = [{**to_citation(state["chunks"][i - 1]), "text": state["chunks"][i - 1]["text"]} for i in used]

    answer = clean_answer(state.get("answer", ""))
    if state.get("clarify"):  # a follow-up question doesn't need a source
        return {"answer": answer, "citations": citations, "trace": ["Asked you for the missing detail"]}
    if not citations or not answer:
        return {"answer": NOT_COVERED, "citations": [], "trace": ["Citation check failed: answer not backed by a policy"]}
    return {"answer": answer, "citations": citations, "trace": [f"Citation check passed: {len(citations)} source(s)"]}


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
    g.add_node("override", override)
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
                             "not_covered": "not_covered", "override": "override"})
    g.add_edge("override", "policy_qa")
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
