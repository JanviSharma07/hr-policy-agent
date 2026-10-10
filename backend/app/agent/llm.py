import json
import time
from functools import lru_cache
from google import genai
from google.genai import errors, types
from app.config import GEMINI_API_KEY, GEMINI_MODEL, GEMINI_FALLBACK_MODELS

RETRYABLE = {429, 500, 503, 504}   # busy / rate-limited / temporary server errors
ATTEMPTS_PER_MODEL = 3


@lru_cache
def get_client() -> genai.Client:
    return genai.Client(
        api_key=GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=60_000),  # milliseconds: give up after 60 s
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


def generate_json(system: str, prompt: str) -> dict:
    last_error = None
    for model in [GEMINI_MODEL, *GEMINI_FALLBACK_MODELS]:
        for attempt in range(ATTEMPTS_PER_MODEL):
            try:
                return json.loads(_call(model, system, prompt))
            except errors.APIError as e:
                if e.code not in RETRYABLE:
                    raise                      # real error (bad key, bad request): stop
                last_error = e
                time.sleep(2 ** attempt)       # wait 1 s, 2 s, 4 s before retrying
    raise RuntimeError(f"Gemini is busy, tried all models: {last_error}")