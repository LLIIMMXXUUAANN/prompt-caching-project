"""CLI comparing Gemini 2.5 Flash caching modes: no-cache, implicit, explicit."""

from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
from google import genai

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
    total_thinking_tokens: int = 0
    total_cost: float = 0.0
    total_latency: float = 0.0
    call_count: int = 0

    def record(self, result: gemini_cache.GenerationResult) -> None:
        self.total_prompt_tokens += result.prompt_tokens
        self.total_cached_tokens += result.cached_tokens
        self.total_output_tokens += result.output_tokens
        self.total_thinking_tokens += result.thinking_tokens
        self.total_cost += pricing.estimate_generation_cost(
            prompt_tokens=result.prompt_tokens,
            cached_tokens=result.cached_tokens,
            output_tokens=result.output_tokens,
            thinking_tokens=result.thinking_tokens,
        )
        self.total_latency += result.latency_seconds
        self.call_count += 1

    @property
    def average_latency(self) -> float:
        return self.total_latency / self.call_count if self.call_count else 0.0


@dataclass
class ExplicitCacheOverhead:
    """One-time and time-based costs of the explicit cache itself.

    Kept separate from ModeStats.total_cost (the per-question generation
    cost) so the table shows exactly what per-question caching saves,
    without silently folding in the cost of creating/storing the cache.
    """

    token_count: int
    seconds_alive: float
    creation_cost: float
    storage_cost: float

    @property
    def total(self) -> float:
        return self.creation_cost + self.storage_cost


def _run_uncached_mode(client: genai.Client, doc_text: str, mode_name: str) -> ModeStats:
    # Shared by "No cache" and "Implicit cache": both modes make the exact
    # same API call and only differ in label — the whole point is that
    # implicit caching isn't a distinct code path, just an automatic,
    # unguaranteed server-side behavior observed on ordinary calls.
    stats = ModeStats(mode_name=mode_name)
    for question in QUESTIONS:
        try:
            result = gemini_cache.generate_without_cache(client, doc_text, question)
        except Exception as exc:
            print(f"  [{mode_name}] question failed: {question!r} -> {exc}")
            continue
        stats.record(result)
    return stats


def run_no_cache_mode(client: genai.Client, doc_text: str) -> ModeStats:
    return _run_uncached_mode(client, doc_text, "No cache")


def run_implicit_cache_mode(client: genai.Client, doc_text: str) -> ModeStats:
    return _run_uncached_mode(client, doc_text, "Implicit cache")


def run_explicit_cache_mode(
    client: genai.Client, doc_text: str, ttl_seconds: int
) -> tuple[ModeStats, ExplicitCacheOverhead | None]:
    stats = ModeStats(mode_name="Explicit cache")
    token_count = gemini_cache.count_tokens(client, doc_text)
    if token_count < gemini_cache.EXPLICIT_CACHE_MIN_TOKENS:
        print(
            f"  Document is {token_count} tokens, below the "
            f"{gemini_cache.EXPLICIT_CACHE_MIN_TOKENS}-token minimum for explicit "
            "caching. Skipping explicit cache mode."
        )
        return stats, None

    cache = gemini_cache.create_explicit_cache(client, doc_text, ttl_seconds)
    # cache.name is Optional per the SDK's type stub, but the API always
    # populates it on a successful create() call; fail loudly if that ever
    # changes rather than silently passing None into downstream calls.
    if cache.name is None:
        raise RuntimeError("Explicit cache was created without a name (unexpected API response)")
    # Prefer the cache's own authoritative token count (what Google actually
    # billed for creation/storage) over the pre-flight estimate used only for
    # the min-token gate above — they can differ slightly since the SDK wraps
    # doc_text in a Content/Part structure with its own small overhead.
    billed_token_count = (
        cache.usage_metadata.total_token_count
        if cache.usage_metadata and cache.usage_metadata.total_token_count
        else token_count
    )
    # Creating the cache means Google processes doc_text for the first time,
    # billed at the standard input rate (not the discounted cached rate).
    creation_cost = pricing.estimate_cache_creation_cost(billed_token_count)
    created_at = time.monotonic()

    try:
        for question in QUESTIONS:
            try:
                result = gemini_cache.generate_with_cache(client, cache.name, question)
            except Exception as exc:
                print(f"  [Explicit cache] question failed: {question!r} -> {exc}")
                continue
            stats.record(result)
    finally:
        # Always release the cache, even on an unexpected error mid-loop,
        # so it doesn't sit around accruing storage cost until its TTL expires.
        seconds_alive = time.monotonic() - created_at
        gemini_cache.delete_cache(client, cache.name)

    storage_cost = pricing.estimate_cache_storage_cost(
        cached_tokens=billed_token_count, seconds_alive=seconds_alive
    )
    overhead = ExplicitCacheOverhead(
        token_count=billed_token_count,
        seconds_alive=seconds_alive,
        creation_cost=creation_cost,
        storage_cost=storage_cost,
    )
    return stats, overhead


def print_comparison_table(modes: list[ModeStats]) -> None:
    header = (
        f"{'Mode':<16} {'Calls':>6} {'Prompt tok':>11} {'Cached tok':>11} "
        f"{'Output tok':>11} {'Think tok':>10} {'Avg latency':>12} {'Est. cost':>10}"
    )
    print()
    print(header)
    print("-" * len(header))
    for stats in modes:
        print(
            f"{stats.mode_name:<16} {stats.call_count:>6} "
            f"{stats.total_prompt_tokens:>11} {stats.total_cached_tokens:>11} "
            f"{stats.total_output_tokens:>11} {stats.total_thinking_tokens:>10} "
            f"{stats.average_latency:>11.2f}s ${stats.total_cost:>9.6f}"
        )
    print()


def print_explicit_cache_overhead(stats: ModeStats, overhead: ExplicitCacheOverhead | None) -> None:
    if overhead is None:
        return
    grand_total = stats.total_cost + overhead.total
    print("Explicit cache overhead (not included in the table's Est. cost column):")
    print(
        f"  Cache creation  ({overhead.token_count} tokens, billed at input rate): "
        f"${overhead.creation_cost:.6f}"
    )
    print(f"  Cache storage   (alive {overhead.seconds_alive:.1f}s): ${overhead.storage_cost:.6f}")
    print(f"  Per-question usage (from table above): ${stats.total_cost:.6f}")
    print(f"  Total explicit cache cost: ${grand_total:.6f}")
    print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--doc", type=Path, default=DEFAULT_DOC_PATH, help="Path to the document to query"
    )
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
    explicit_stats, explicit_overhead = run_explicit_cache_mode(client, doc_text, args.ttl)

    print_comparison_table([no_cache_stats, implicit_stats, explicit_stats])
    print_explicit_cache_overhead(explicit_stats, explicit_overhead)
    print("Done.")


if __name__ == "__main__":
    main()
