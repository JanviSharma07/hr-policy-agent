import json
import logging
import time
from functools import lru_cache
from google import genai
from google.genai import errors, types
from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_FAST_MODEL

log = logging.getLogger("uvicorn.error")  # shows up in the uvicorn terminal

RETRYABLE = {429, 500, 503, 504}   # busy / rate-limited / temporary server errors
ATTEMPTS_PER_MODEL = 2
TIMEOUT_MS = 30_000                # give up on one call after 30 s and try the next model


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=TIMEOUT_MS),
    )


def _call(model: str, system: str, prompt: str) -> str:
    response = get_client().models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            response_mime_type="application/json",
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        ),
    )
    return response.text


def _is_temporary(error: Exception) -> bool:
    if isinstance(error, errors.APIError):
        return error.code in RETRYABLE
    if isinstance(error, json.JSONDecodeError):
        return True  # the model returned broken JSON: just ask again
    name = type(error).__name__.lower()
    return "timeout" in name or "timed out" in str(error).lower()


def _models(fast: bool) -> list[str]:
    order = ([GEMINI_FAST_MODEL] if fast else []) + [GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]
    return list(dict.fromkeys(m for m in order if m))  # drop duplicates, keep order


def generate_json(system: str, prompt: str, fast: bool = False, label: str = "agent") -> dict:
    """fast=True uses the small, quick model first (for routing and rewriting).
    Answers keep using the main model."""
    last_error = None
    for model in _models(fast):
        for attempt in range(ATTEMPTS_PER_MODEL):
            start = time.perf_counter()
            try:
                result = json.loads(_call(model, system, prompt))
                log.info("Gemini %-11s %-24s %5.1fs", label, model, time.perf_counter() - start)
                return result
            except Exception as e:
                if not _is_temporary(e):
                    raise                  # real error (bad key, bad request): stop
                last_error = e
                log.warning("Gemini %-11s %-24s failed after %.1fs (%s), retrying",
                            label, model, time.perf_counter() - start, type(e).__name__)
                time.sleep(1 + attempt)
    raise RuntimeError(f"Gemini is busy, tried all models: {last_error}")
