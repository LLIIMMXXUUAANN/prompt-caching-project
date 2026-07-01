# Gemini Caching Comparison CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python CLI that runs the same batch of questions against a bundled document three ways — no caching, implicit (automatic) caching, and explicit (`CachedContent`) caching against Gemini 2.5 Flash — prints a cost/latency comparison table, and optionally drops into an interactive chat against the explicit cache so the TTL expiry can be observed live.

**Architecture:** Flat, four-module script project (`gemini_cache.py` for all Gemini SDK calls, `pricing.py` for pure token→cost math, `questions.py` for the fixed question list, `main.py` for orchestration + CLI), plus a bundled `sample_doc.txt`. Only `pricing.py` gets automated unit tests (it's the only pure, network-free logic); everything else is verified by manual end-to-end runs against the live API, per the spec's testing rationale.

**Tech Stack:** Python 3.13, `uv` for project/dependency management, `google-genai` SDK, `python-dotenv`, `ruff` for lint/format, `ty` for type checking, `pytest` for the pricing unit tests.

**Notes on deviation from spec:**
- The spec's design doc estimated an ~8-10k token sample document "for realism." This plan uses a ~1,300-word original article (~1,600-1,800 tokens) instead — comfortably above the ~1,024-token explicit-caching minimum with margin, but small enough to keep API costs and iteration time low while learning. The code still performs a runtime token-count check (Task 5) and degrades gracefully if a swapped-in `--doc` file is too small, so this doesn't weaken the design.
- The spec listed `requirements.txt` for dependency management. This plan uses `pyproject.toml` + `uv.lock` via `uv` instead (per the project's modern-python tooling convention) — same runtime dependencies (`google-genai`, `python-dotenv`), just managed with the current standard tool rather than a flat pip requirements file.

---

### Task 1: Project scaffolding with uv

**Files:**
- Create: `pyproject.toml` (via `uv init --bare`, then edited)
- Create: `.python-version` (created automatically by `uv init`)
- Create: `.env.example`
- Modify: `.gitignore` (already has `.env`, `__pycache__/`, `*.pyc`, `.venv/` — add `uv.lock` exclusion is NOT needed, `uv.lock` should be committed)

- [ ] **Step 1: Initialize the uv project**

Run: `uv init --bare --name prompt-caching-project`

Expected: creates `pyproject.toml` and `.python-version` in the current directory. Does not overwrite existing files (`.env`, `.gitignore`, `docs/`).

- [ ] **Step 2: Add runtime dependencies**

Run: `uv add google-genai python-dotenv`

Expected: `pyproject.toml`'s `[project.dependencies]` now lists `google-genai` and `python-dotenv`; `uv.lock` and `.venv/` are created.

- [ ] **Step 3: Add dev dependencies**

Run: `uv add --group dev ruff ty pytest`

Expected: `pyproject.toml` gains a `[dependency-groups]` section with `dev = [...]` listing `ruff`, `ty`, `pytest`.

- [ ] **Step 4: Add tool configuration to pyproject.toml**

Read the current `pyproject.toml` first, then append this configuration:

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]

[tool.ty.environment]
python-version = "3.11"
```

- [ ] **Step 5: Create `.env.example`**

```
# Get a key at https://aistudio.google.com/apikey
GEMINI_API_KEY=
```

- [ ] **Step 6: Verify the environment installs cleanly**

Run: `uv sync --all-groups`

Expected: exits 0, `.venv/` populated, no errors.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .python-version uv.lock .env.example
git commit -m "Scaffold uv project with google-genai, ruff, ty, pytest"
```

---

### Task 2: Sample document and question set

**Files:**
- Create: `sample_doc.txt`
- Create: `questions.py`

- [ ] **Step 1: Create `sample_doc.txt`**

```
The Global Story of Coffee: From Ethiopian Highlands to Your Morning Cup

According to legend, coffee's stimulating properties were first discovered in the highlands of Ethiopia by a goat herder named Kaldi. As the story goes, Kaldi noticed that his goats became unusually energetic after eating the red berries of a certain shrub, and stayed awake through the night. Curious, Kaldi brought the berries to a local monastery, where a monk experimented with them and found that a drink made from the berries kept him alert through long hours of evening prayer. Word of the energizing berries spread first through nearby monasteries, then across the region, though historians note the tale of Kaldi and his goats was not written down until centuries after these events supposedly took place, and should be read as folklore rather than documented history.

From Ethiopia, cultivation and trade of coffee moved north across the Red Sea into Yemen by the fifteenth century, where Sufi monasteries used the drink to stay awake during nighttime devotions. Yemeni traders, particularly through the port of Mocha, controlled the coffee trade for roughly two hundred years, and it was from Yemen that coffee spread into the wider Ottoman Empire. Coffeehouses opened in Cairo, Damascus, and Istanbul, becoming centers of conversation, chess, and political discussion — so much so that rulers periodically tried to ban them, fearing they were breeding grounds for dissent. By the seventeenth century, coffee had reached Venice via Mediterranean trade routes, and coffeehouses soon followed in London, Paris, and Vienna, where they became fixtures of intellectual and commercial life.

Botanically, almost all coffee consumed today comes from just two species of the genus Coffea: Coffea arabica and Coffea canephora, the latter more commonly known as Robusta. Arabica is generally considered to produce a smoother, more aromatic cup with lower caffeine content, while Robusta plants are hardier, more disease-resistant, and produce beans with a stronger, more bitter flavor and roughly double the caffeine. Of the world's coffee production, Arabica accounts for approximately 60 to 70 percent, with Robusta making up most of the remainder; Robusta is especially dominant in instant coffee and espresso blends where its higher caffeine content and lower cost are valued.

Both species grow best within what growers call the "coffee belt," a band of the globe roughly between the Tropic of Cancer and the Tropic of Capricorn, where the climate provides the consistent warmth, rainfall, and lack of frost that coffee plants require. Within this belt, Arabica in particular is prized when grown at higher elevations, typically between 600 and 2,000 meters above sea level. The cooler temperatures at these altitudes slow the ripening of the coffee cherries, which growers and roasters generally believe concentrates more complex sugars and acids in the bean. Major growing regions include Brazil and Colombia in South America, Ethiopia and Kenya in Africa, and Vietnam and Indonesia in Southeast Asia; Brazil alone produces roughly a third of the world's coffee, while Vietnam is the largest producer of Robusta.

Once coffee cherries are harvested, they must be processed to separate the seed — the coffee bean — from the fruit surrounding it, and the method used has a significant effect on the final flavor. There are two primary processing methods. In the washed (or "wet") process, the outer skin and fruit pulp are mechanically removed shortly after harvest, and the beans are then fermented in water for a period of hours to break down the remaining mucilage before being rinsed and dried. This method tends to produce a cleaner, brighter, more acidic cup, since less of the fruit's sugars remain in contact with the bean during drying. In the natural (or "dry") process, by contrast, the whole cherry is dried in the sun for one to several weeks with the fruit still intact around the bean, and only later is the dried fruit hull removed. Because the bean spends much longer in contact with the sugars of the fruit, the natural process typically produces a heavier-bodied, fruitier, sometimes wine-like cup. A third, hybrid method known as honey processing removes the skin but leaves some or all of the sticky mucilage on the bean during drying, producing characteristics somewhere between the two primary methods.

After processing, green (unroasted) coffee beans are roasted before they can be brewed, and roasting is where much of coffee's characteristic flavor and aroma develops. As beans heat, they undergo the Maillard reaction — the same browning reaction responsible for the crust on bread and the sear on meat — along with caramelization of sugars, both of which produce hundreds of new aromatic compounds. Roasters listen for two audible markers during the process: "first crack," an audible popping sound that occurs as moisture trapped inside the bean turns to steam and the bean's structure begins to break down, and, at higher temperatures, "second crack," a quieter, more rapid cracking caused by the release of oils and gases as the bean's cellular structure breaks down further. Light roasts are typically stopped shortly after first crack and preserve more of the bean's original acidity and origin flavor; medium roasts are taken further, balancing acidity with more developed sweetness; and dark roasts are carried through or past second crack, producing bold, often smoky or bitter flavors while masking more of the bean's original character.

Coffee's best-known chemical property is, of course, caffeine, a stimulant that works primarily by blocking adenosine receptors in the brain, a mechanism that reduces the sensation of tiredness. Caffeine has an approximate half-life in the human body of five to six hours, meaning that roughly half of the caffeine consumed is still present in the bloodstream five to six hours after consumption — one reason sleep specialists often recommend avoiding coffee in the afternoon. Beyond caffeine, coffee also contains chlorogenic acids, a family of antioxidant compounds that contribute to the drink's bitterness and are gradually broken down during roasting; darker roasts, having been exposed to heat for longer, generally contain lower levels of chlorogenic acids than lighter roasts.

How coffee is brewed also substantially affects the character of the final cup, and different methods extract the soluble compounds from ground coffee in different ways. Espresso forces hot water through finely ground, tightly packed coffee under high pressure, typically nine bars or more, over a short period of roughly twenty-five to thirty seconds, producing a concentrated shot topped with a layer of foam called crema. Pour-over brewing, by contrast, involves slowly pouring hot water over medium-ground coffee held in a paper or cloth filter, allowing gravity to draw the water through; the recommended water temperature for pour-over brewing is between 195 and 205 degrees Fahrenheit (roughly 90 to 96 degrees Celsius), since water that is too cool under-extracts the grounds and produces a sour, weak cup, while water that is too hot over-extracts and produces excessive bitterness. The French press, or cafetière, steeps coarsely ground coffee directly in hot water for several minutes before a mesh plunger separates the grounds from the liquid, producing a fuller-bodied cup than paper-filtered methods since more oils pass through the mesh filter. Cold brew departs from all of these methods by using no heat at all: coarsely ground coffee is steeped in room-temperature or cold water for twelve to twenty-four hours, a slow extraction that produces a smoother, less acidic concentrate, typically diluted with water or milk before serving.

In recent decades, a "specialty coffee" movement has emerged alongside the traditional commodity coffee trade, emphasizing traceability back to individual farms or cooperatives, careful attention to processing method and roast, and direct trade relationships intended to pay growers a larger share of the final retail price. Certification programs such as Fair Trade and Rainforest Alliance have also grown alongside this movement, aiming to guarantee minimum prices or environmental standards for farmers, though these programs remain a small fraction of overall global coffee trade, which is still dominated by large-scale commodity production in Brazil, Vietnam, Colombia, and Indonesia.
```

- [ ] **Step 2: Create `questions.py`**

```python
"""Fixed set of questions asked against sample_doc.txt across all caching modes."""

QUESTIONS = [
    "According to the document, which two Coffea species dominate global coffee "
    "production, and roughly what share of the world's coffee does Arabica represent?",
    "What water temperature range does the document recommend for pour-over brewing?",
    "What is the approximate half-life of caffeine in the human body according to the document?",
    "What are the two primary cherry processing methods described in the document, "
    "and what is one key difference between them?",
    "According to the legend recounted in the document, who is credited with "
    "discovering coffee's stimulating effects, and what animals were involved?",
    "What altitude range does the document associate with high-quality Arabica cultivation?",
]
```

- [ ] **Step 3: Verify token count clears the explicit-caching minimum**

Run: `uv run python -c "print(len(open('sample_doc.txt', encoding='utf-8').read().split()))"`

Expected: a word count around 1,100–1,400 (comfortably enough to exceed ~1,024 tokens once tokenized — this is a rough sanity check; the real check happens via the API's tokenizer in Task 5).

- [ ] **Step 4: Commit**

```bash
git add sample_doc.txt questions.py
git commit -m "Add bundled sample document and fixed question set"
```

---

### Task 3: pricing.py with unit tests (TDD)

**Files:**
- Create: `pricing.py`
- Test: `tests/test_pricing.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pricing.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_pricing.py -v`

Expected: FAIL — `ModuleNotFoundError: No module named 'pricing'` (file doesn't exist yet).

- [ ] **Step 3: Implement `pricing.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pricing.py -v`

Expected: PASS — 5 passed.

- [ ] **Step 5: Commit**

```bash
git add pricing.py tests/test_pricing.py
git commit -m "Add pricing module with unit-tested cost estimation"
```

---

### Task 4: gemini_cache.py — Gemini SDK wrapper

**Files:**
- Create: `gemini_cache.py`

- [ ] **Step 1: Implement `gemini_cache.py`**

```python
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
    return response.total_tokens


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
```

- [ ] **Step 2: Manual smoke test — verify API connectivity and token counting**

Run:
```bash
uv run python -c "
from gemini_cache import get_client, count_tokens
client = get_client()
doc = open('sample_doc.txt', encoding='utf-8').read()
print(count_tokens(client, doc))
"
```

Expected: prints a single integer greater than 1024 (confirms `GEMINI_API_KEY` works and the sample doc clears the explicit-caching minimum). If this errors with an auth error, check `.env` has a valid key and that `main.py`'s `load_dotenv()` isn't needed here since we're calling `get_client()` directly — if the key isn't already exported in your shell, run `uv run --env-file .env python -c "..."` instead, or `export $(cat .env | xargs)` first.

- [ ] **Step 3: Commit**

```bash
git add gemini_cache.py
git commit -m "Add gemini_cache wrapper for no-cache/explicit-cache SDK calls"
```

---

### Task 5: main.py — orchestration, comparison table, interactive chat

**Files:**
- Create: `main.py`

- [ ] **Step 1: Implement `main.py`**

```python
"""CLI comparing Gemini 2.5 Flash caching modes: no-cache, implicit, explicit."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

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
        except Exception as exc:  # noqa: BLE001 - keep the demo loop going on any single failure
            print(f"  [No cache] question failed: {question!r} -> {exc}")
            continue
        stats.record(result)
    return stats


def run_implicit_cache_mode(client, doc_text: str) -> ModeStats:
    stats = ModeStats(mode_name="Implicit cache")
    for question in QUESTIONS:
        try:
            result = gemini_cache.generate_without_cache(client, doc_text, question)
        except Exception as exc:  # noqa: BLE001
            print(f"  [Implicit cache] question failed: {question!r} -> {exc}")
            continue
        stats.record(result)
    return stats


def run_explicit_cache_mode(
    client, doc_text: str, ttl_seconds: int
) -> tuple[ModeStats, object | None]:
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
    for question in QUESTIONS:
        try:
            result = gemini_cache.generate_with_cache(client, cache.name, question)
        except Exception as exc:  # noqa: BLE001
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
        except Exception as exc:  # noqa: BLE001 - cache expiry surfaces here
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
    parser.add_argument(
        "--no-chat", action="store_true", help="Skip the interactive chat tail"
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
    explicit_stats, cache = run_explicit_cache_mode(client, doc_text, args.ttl)

    print_comparison_table([no_cache_stats, implicit_stats, explicit_stats])

    if cache is None:
        return

    if not args.no_chat:
        interactive_chat(client, cache.name, cache.expire_time, args.ttl)

    gemini_cache.delete_cache(client, cache.name)
    print("Explicit cache deleted. Done.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Manual end-to-end run**

Run: `uv run python main.py --no-chat`

Expected:
- Prints "Loaded document: ... (N characters)"
- Prints "Mode 1/3", "Mode 2/3", "Mode 3/3" progress lines in order
- Prints a comparison table with 3 rows (No cache / Implicit cache / Explicit cache), each showing 6 calls, nonzero prompt tokens, and a dollar cost
- The Explicit cache row's "Cached tok" column is nonzero (guaranteed by the API)
- The Implicit cache row's "Cached tok" column may be zero or nonzero — this is expected and is the point of the demo: implicit caching isn't guaranteed, only observed
- Ends with "Explicit cache deleted. Done."

If any question fails, the script should print which one and continue rather than crashing — verify this by temporarily breaking your network mid-run if you want to see the error-handling path, then restore it.

- [ ] **Step 3: Manual interactive/TTL verification**

Run: `uv run python main.py --ttl 30`

After the comparison table prints, the chat prompt appears. Ask one question immediately (should succeed, showing token/cost stats), then wait about 35 seconds and ask another question. Expected: the second call either succeeds (server hasn't evicted yet) or fails with "Cache call failed (it may have expired)" followed by a clean exit — not a stack trace.

- [ ] **Step 4: Commit**

```bash
git add main.py
git commit -m "Add main CLI: 3-way cache comparison plus interactive chat tail"
```

---

### Task 6: README and final lint pass

**Files:**
- Create: `README.md`

- [ ] **Step 1: Create `README.md`**

```markdown
# Gemini Caching Comparison

A small learning project comparing Gemini 2.5 Flash's caching modes:

- **No cache** — every question re-sends the full document as context.
- **Implicit cache** — identical calls to "no cache," but observing Google's
  automatic prefix caching via `cached_content_token_count` in the response.
- **Explicit cache** — creates a `CachedContent` resource once via the
  `google-genai` SDK and references it for every question.

## Setup

1. Copy `.env.example` to `.env` and add your Gemini API key
   (get one at https://aistudio.google.com/apikey).
2. Install dependencies: `uv sync --all-groups`

## Usage

Run the full comparison plus interactive chat:

```bash
uv run python main.py
```

Skip the interactive chat tail:

```bash
uv run python main.py --no-chat
```

Use your own document, and set a custom cache TTL (seconds):

```bash
uv run python main.py --doc /path/to/file.txt --ttl 120
```

## Development

```bash
uv run pytest              # unit tests (pricing.py only — everything else needs a live API)
uv run ruff check .        # lint
uv run ruff format .       # format
uv run ty check .          # type check
```

## Manual verification checklist

Since most of this project talks to a live external API, there's no
automated test suite beyond `pricing.py`. Verify by running:

- [ ] `uv run python main.py --no-chat` prints a 3-row comparison table with
      nonzero prompt tokens per row and a nonzero "Cached tok" value on the
      Explicit cache row.
- [ ] `uv run python main.py --ttl 30`, then wait ~35s mid-chat and ask
      another question — confirm a clean "cache expired" message rather than
      a crash.
```

- [ ] **Step 2: Run full lint and test suite**

Run: `uv run ruff format . && uv run ruff check . && uv run ty check . && uv run pytest`

Expected: formatter makes no further changes (or apply them if it does), ruff reports no errors, ty reports no errors, pytest shows 5 passed.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "Add README with setup, usage, and manual verification checklist"
```
