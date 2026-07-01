"""Thin wrapper around the google-genai SDK for the caching comparison demo."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass

from google import genai
from google.genai import types

MODEL_NAME = "gemini-2.5-flash"
EXPLICIT_CACHE_MIN_TOKENS = 1024


class MissingApiKeyError(RuntimeError):
    """Raised when GEMINI_API_KEY is not set in the environment."""


@dataclass
class GenerationResult:
    text: str
    prompt_tokens: int
    cached_tokens: int
    output_tokens: int
    latency_seconds: float


def get_client() -> genai.Client:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise MissingApiKeyError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key."
        )
    return genai.Client(api_key=api_key)


def count_tokens(client: genai.Client, text: str) -> int:
    response = client.models.count_tokens(model=MODEL_NAME, contents=text)
    return response.total_tokens or 0


def _to_result(response, elapsed_seconds: float) -> GenerationResult:
    usage = response.usage_metadata
    return GenerationResult(
        text=response.text,
        prompt_tokens=usage.prompt_token_count,
        cached_tokens=usage.cached_content_token_count or 0,
        output_tokens=usage.candidates_token_count,
        latency_seconds=elapsed_seconds,
    )


def generate_without_cache(
    client: genai.Client, doc_text: str, question: str
) -> GenerationResult:
    start = time.monotonic()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=[doc_text, question],
    )
    return _to_result(response, time.monotonic() - start)


def create_explicit_cache(client: genai.Client, doc_text: str, ttl_seconds: int):
    return client.caches.create(
        model=MODEL_NAME,
        config=types.CreateCachedContentConfig(
            contents=[
                types.Content(role="user", parts=[types.Part.from_text(text=doc_text)])
            ],
            display_name="prompt-caching-demo",
            ttl=f"{ttl_seconds}s",
        ),
    )


def generate_with_cache(
    client: genai.Client, cache_name: str, question: str
) -> GenerationResult:
    start = time.monotonic()
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=question,
        config=types.GenerateContentConfig(cached_content=cache_name),
    )
    return _to_result(response, time.monotonic() - start)


def delete_cache(client: genai.Client, cache_name: str) -> None:
    client.caches.delete(name=cache_name)
