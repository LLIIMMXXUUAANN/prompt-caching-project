from pricing import estimate_cache_storage_cost, estimate_generation_cost


def test_no_cache_bills_full_input_and_output_rates():
    cost = estimate_generation_cost(
        prompt_tokens=1_000_000, cached_tokens=0, output_tokens=1_000_000
    )
    assert cost == 0.30 + 2.50


def test_fully_cached_prompt_bills_cached_rate_only():
    cost = estimate_generation_cost(
        prompt_tokens=1_000_000, cached_tokens=1_000_000, output_tokens=0
    )
    assert cost == 0.075


def test_partial_cache_is_cheaper_than_no_cache():
    baseline = estimate_generation_cost(
        prompt_tokens=10_000, cached_tokens=0, output_tokens=200
    )
    with_cache = estimate_generation_cost(
        prompt_tokens=10_000, cached_tokens=9_000, output_tokens=200
    )
    assert with_cache < baseline


def test_cache_storage_cost_scales_with_time():
    one_hour = estimate_cache_storage_cost(cached_tokens=1_000_000, seconds_alive=3600)
    two_hours = estimate_cache_storage_cost(cached_tokens=1_000_000, seconds_alive=7200)
    assert one_hour == 1.00
    assert two_hours == 2.00


def test_cache_storage_cost_zero_time_is_free():
    cost = estimate_cache_storage_cost(cached_tokens=1_000_000, seconds_alive=0)
    assert cost == 0.0
