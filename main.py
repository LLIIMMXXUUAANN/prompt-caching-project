"""CLI comparing Gemini 2.5 Flash caching modes: no-cache, implicit, explicit."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from google.genai import types

import gemini_cache
import pricing
from questions import QUESTIONS

DEFAULT_DOC_PATH = Path(__file__).parent / "sample_doc.txt"
DEFAULT_TTL_SECONDS = 300


@dataclass
class ModeStats:
    mode_name: str
    total_prompt_tokens: int = 0
    total_cached_tokens: int = 0
    total_output_tokens: int = 0
    total_cost: float = 0.0
    total_latency: float = 0.0
    call_count: int = 0

    def record(self, result: gemini_cache.GenerationResult) -> None:
        self.total_prompt_tokens += result.prompt_tokens
        self.total_cached_tokens += result.cached_tokens
        self.total_output_tokens += result.output_tokens
        self.total_cost += pricing.estimate_generation_cost(
            prompt_tokens=result.prompt_tokens,
            cached_tokens=result.cached_tokens,
            output_tokens=result.output_tokens,
        )
        self.total_latency += result.latency_seconds
        self.call_count += 1

    @property
    def average_latency(self) -> float:
        return self.total_latency / self.call_count if self.call_count else 0.0


def run_no_cache_mode(client, doc_text: str) -> ModeStats:
    stats = ModeStats(mode_name="No cache")
    for question in QUESTIONS:
        try:
            result = gemini_cache.generate_without_cache(client, doc_text, question)
        except Exception as exc:
            print(f"  [No cache] question failed: {question!r} -> {exc}")
            continue
        stats.record(result)
    return stats


def run_implicit_cache_mode(client, doc_text: str) -> ModeStats:
    stats = ModeStats(mode_name="Implicit cache")
    for question in QUESTIONS:
        try:
            result = gemini_cache.generate_without_cache(client, doc_text, question)
        except Exception as exc:
            print(f"  [Implicit cache] question failed: {question!r} -> {exc}")
            continue
        stats.record(result)
    return stats


def run_explicit_cache_mode(
    client, doc_text: str, ttl_seconds: int
) -> tuple[ModeStats, types.CachedContent | None]:
    stats = ModeStats(mode_name="Explicit cache")
    token_count = gemini_cache.count_tokens(client, doc_text)
    if token_count < gemini_cache.EXPLICIT_CACHE_MIN_TOKENS:
        print(
            f"  Document is {token_count} tokens, below the "
            f"{gemini_cache.EXPLICIT_CACHE_MIN_TOKENS}-token minimum for explicit "
            "caching. Skipping explicit cache mode and interactive chat."
        )
        return stats, None

    cache = gemini_cache.create_explicit_cache(client, doc_text, ttl_seconds)
    # cache.name is Optional per the SDK's type stub, but the API always
    # populates it on a successful create() call; fail loudly if that ever
    # changes rather than silently passing None into downstream calls.
    if cache.name is None:
        raise RuntimeError("Explicit cache was created without a name (unexpected API response)")

    for question in QUESTIONS:
        try:
            result = gemini_cache.generate_with_cache(client, cache.name, question)
        except Exception as exc:
            print(f"  [Explicit cache] question failed: {question!r} -> {exc}")
            continue
        stats.record(result)
    return stats, cache


def print_comparison_table(modes: list[ModeStats]) -> None:
    header = (
        f"{'Mode':<16} {'Calls':>6} {'Prompt tok':>11} {'Cached tok':>11} "
        f"{'Output tok':>11} {'Avg latency':>12} {'Est. cost':>10}"
    )
    print()
    print(header)
    print("-" * len(header))
    for stats in modes:
        print(
            f"{stats.mode_name:<16} {stats.call_count:>6} "
            f"{stats.total_prompt_tokens:>11} {stats.total_cached_tokens:>11} "
            f"{stats.total_output_tokens:>11} {stats.average_latency:>11.2f}s "
            f"${stats.total_cost:>9.6f}"
        )
    print()


def interactive_chat(client, cache_name: str, cache_expire_time, ttl_seconds: int) -> None:
    print("Entering interactive chat against the explicit cache.")
    print(f"Cache expires at {cache_expire_time} (TTL {ttl_seconds}s). Type 'quit' to exit.")
    running_cost = 0.0
    while True:
        try:
            question = input("> ").strip()
        except EOFError:
            break
        if question.lower() in {"quit", "exit"}:
            break
        if not question:
            continue
        try:
            result = gemini_cache.generate_with_cache(client, cache_name, question)
        except Exception as exc:
            print(f"Cache call failed (it may have expired): {exc}")
            print("Exiting interactive chat.")
            break
        cost = pricing.estimate_generation_cost(
            prompt_tokens=result.prompt_tokens,
            cached_tokens=result.cached_tokens,
            output_tokens=result.output_tokens,
        )
        running_cost += cost
        print(result.text)
        print(
            f"  [tokens: {result.prompt_tokens} prompt / {result.cached_tokens} cached / "
            f"{result.output_tokens} output | cost: ${cost:.6f} | "
            f"running total: ${running_cost:.6f}]"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--doc", type=Path, default=DEFAULT_DOC_PATH, help="Path to the document to query"
    )
    parser.add_argument("--no-chat", action="store_true", help="Skip the interactive chat tail")
    parser.add_argument(
        "--ttl", type=int, default=DEFAULT_TTL_SECONDS, help="Explicit cache TTL in seconds"
    )
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    try:
        client = gemini_cache.get_client()
    except gemini_cache.MissingApiKeyError as exc:
        print(f"Error: {exc}")
        raise SystemExit(1) from exc

    doc_text = args.doc.read_text(encoding="utf-8")

    print(f"Loaded document: {args.doc} ({len(doc_text)} characters)")
    print(f"Running {len(QUESTIONS)} questions against 3 caching modes...\n")

    print("Mode 1/3: No cache baseline...")
    no_cache_stats = run_no_cache_mode(client, doc_text)

    print("Mode 2/3: Implicit cache (same calls, observing automatic cache hits)...")
    implicit_stats = run_implicit_cache_mode(client, doc_text)

    print("Mode 3/3: Explicit cache...")
    explicit_stats, cache = run_explicit_cache_mode(client, doc_text, args.ttl)

    print_comparison_table([no_cache_stats, implicit_stats, explicit_stats])

    if cache is None:
        return
    assert cache.name is not None  # guaranteed by run_explicit_cache_mode's own check

    if not args.no_chat:
        interactive_chat(client, cache.name, cache.expire_time, args.ttl)

    gemini_cache.delete_cache(client, cache.name)
    print("Explicit cache deleted. Done.")


if __name__ == "__main__":
    main()
