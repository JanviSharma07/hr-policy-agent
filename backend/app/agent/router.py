from functools import lru_cache
from app.config import ROUTER_DIR
from app.agent.llm import generate_json
from app.agent.prompts import ROUTER_SYSTEM

INTENTS = ["policy_qa", "summarize", "compare", "eligibility", "calculation", "out_of_scope"]


@lru_cache
def _distilbert():
    # The team's fine-tuned DistilBERT, once it's saved in backend/models/router/
    if (ROUTER_DIR / "config.json").exists():
        from transformers import pipeline
        return pipeline("text-classification", model=str(ROUTER_DIR))
    return None


def classify(question: str) -> tuple[str, str]:
    """Returns (intent, which_router_was_used)."""
    model = _distilbert()
    if model is not None:
        intent = model(question)[0]["label"]
        source = "DistilBERT"
    else:
        intent = generate_json(ROUTER_SYSTEM, question).get("intent", "")
        source = "Gemini placeholder"
    return (intent if intent in INTENTS else "policy_qa"), source
