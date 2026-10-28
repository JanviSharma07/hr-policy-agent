import json
import os
import logging
import time
from functools import lru_cache
from google import genai
from google.genai import errors, types
from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS, GEMINI_FAST_MODEL

log = logging.getLogger("uvicorn.error")  # shows up in the uvicorn terminal

RETRYABLE = {429, 500, 503, 504}   # busy / rate-limited / temporary server errors
ROUNDS = 2                         # try every model once, then all of them once more
TIMEOUT_MS = 25_000                # give up on one call after 25 s and try the next model
THINKING = os.getenv("GEMINI_THINKING", "low")  # short "thinking" = much faster answers
_thinking_ok = True                # switched off if this model/SDK doesn't accept it


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=TIMEOUT_MS),
    )


def _config(system: str, thinking: bool) -> types.GenerateContentConfig:
    extra = {}
    if thinking and THINKING:
        extra["thinking_config"] = types.ThinkingConfig(thinking_level=THINKING.upper())
    return types.GenerateContentConfig(
        system_instruction=system,
        temperature=0.2,
        response_mime_type="application/json",
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        **extra,
    )


def _call(model: str, system: str, prompt: str) -> str:
    global _thinking_ok
    if _thinking_ok:
        try:
            return get_client().models.generate_content(
                model=model, contents=prompt, config=_config(system, True)).text
        except Exception as e:  # an older SDK or model that doesn't support thinking levels
            if not ("thinking" in str(e).lower() or isinstance(e, (TypeError, ValueError))):
                raise
            _thinking_ok = False
            log.warning("Gemini thinking level not supported here, continuing without it")
    return get_client().models.generate_content(
        model=model, contents=prompt, config=_config(system, False)).text


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
    for attempt in range(ROUNDS):
        for model in _models(fast):
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
                time.sleep(0.5)
    raise RuntimeError(f"Gemini is busy, tried all models: {last_error}")
