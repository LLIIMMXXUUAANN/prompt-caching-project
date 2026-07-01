"""Cost estimation for Gemini 2.5 Flash token usage.

Rates verified against https://ai.google.dev/gemini-api/docs/pricing on 2026-07-01.
Re-check that page before trusting these numbers for real budgeting — Google
changes model pricing periodically.
"""

INPUT_PRICE_PER_MILLION_TOKENS = 0.30
OUTPUT_PRICE_PER_MILLION_TOKENS = 2.50
CACHED_INPUT_PRICE_PER_MILLION_TOKENS = 0.075
CACHE_STORAGE_PRICE_PER_MILLION_TOKENS_PER_HOUR = 1.00


def estimate_generation_cost(
    prompt_tokens: int, cached_tokens: int, output_tokens: int
) -> float:
    """Estimate USD cost of one generate_content call.

    `cached_tokens` is billed at the discounted rate; the remainder of
    `prompt_tokens` is billed at the standard input rate.
    """
    billed_input_tokens = prompt_tokens - cached_tokens
    input_cost = (billed_input_tokens / 1_000_000) * INPUT_PRICE_PER_MILLION_TOKENS
    cached_cost = (cached_tokens / 1_000_000) * CACHED_INPUT_PRICE_PER_MILLION_TOKENS
    output_cost = (output_tokens / 1_000_000) * OUTPUT_PRICE_PER_MILLION_TOKENS
    return input_cost + cached_cost + output_cost


def estimate_cache_storage_cost(cached_tokens: int, seconds_alive: float) -> float:
    """Estimate USD cost of keeping an explicit cache alive for a duration."""
    hours_alive = seconds_alive / 3600
    return (
        (cached_tokens / 1_000_000)
        * CACHE_STORAGE_PRICE_PER_MILLION_TOKENS_PER_HOUR
        * hours_alive
    )
