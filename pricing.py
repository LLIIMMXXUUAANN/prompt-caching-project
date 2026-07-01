"""Cost estimation for Gemini 2.5 Flash token usage.

Rates verified against https://ai.google.dev/gemini-api/docs/pricing on 2026-07-01.
Re-check that page before trusting these numbers for real budgeting — Google
changes model pricing periodically.
"""

INPUT_PRICE_PER_MILLION_TOKENS = 0.30
OUTPUT_PRICE_PER_MILLION_TOKENS = 2.50
CACHED_INPUT_PRICE_PER_MILLION_TOKENS = 0.03
CACHE_STORAGE_PRICE_PER_MILLION_TOKENS_PER_HOUR = 1.00


def estimate_generation_cost(
    prompt_tokens: int, cached_tokens: int, output_tokens: int, thinking_tokens: int = 0
) -> float:
    """Estimate USD cost of one generate_content call.

    `cached_tokens` is billed at the discounted rate; the remainder of
    `prompt_tokens` is billed at the standard input rate. `thinking_tokens`
    are billed at the same rate as `output_tokens` (Gemini's pricing page
    lists the output rate as "including thinking tokens").
    """
    # Floor at 0: a well-formed response never has cached_tokens > prompt_tokens
    # (cached is a subset of prompt), but don't let a malformed one produce a
    # silently negative cost instead of an obviously-wrong zero.
    billed_input_tokens = max(0, prompt_tokens - cached_tokens)
    input_cost = (billed_input_tokens / 1_000_000) * INPUT_PRICE_PER_MILLION_TOKENS
    cached_cost = (cached_tokens / 1_000_000) * CACHED_INPUT_PRICE_PER_MILLION_TOKENS
    output_cost = ((output_tokens + thinking_tokens) / 1_000_000) * OUTPUT_PRICE_PER_MILLION_TOKENS
    return input_cost + cached_cost + output_cost


def estimate_cache_creation_cost(token_count: int) -> float:
    """Estimate USD cost of the one-time prefill when creating an explicit cache.

    Creating a cache means Google processes that content for the first time,
    so it's billed at the standard input rate — not the discounted cached
    rate, which only applies to later calls that reference the cache.
    """
    return (token_count / 1_000_000) * INPUT_PRICE_PER_MILLION_TOKENS


def estimate_cache_storage_cost(cached_tokens: int, seconds_alive: float) -> float:
    """Estimate USD cost of keeping an explicit cache alive for a duration."""
    hours_alive = seconds_alive / 3600
    return (
        (cached_tokens / 1_000_000) * CACHE_STORAGE_PRICE_PER_MILLION_TOKENS_PER_HOUR * hours_alive
    )
