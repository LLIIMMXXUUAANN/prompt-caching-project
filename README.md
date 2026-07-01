# Gemini Caching Comparison

A small learning project comparing Gemini 2.5 Flash's caching modes:

- **No cache** — every question re-sends the full document as context.
- **Implicit cache** — identical calls to "no cache," but observing Google's
  automatic prefix caching via `cached_content_token_count` in the response.
- **Explicit cache** — creates a `CachedContent` resource once via the
  `google-genai` SDK and references it for every question.

Pricing constants in `pricing.py` are based on
[Gemini 2.5 Flash's official pricing page](https://ai.google.dev/gemini-api/docs/pricing#gemini-2.5-flash) —
check that page for current rates before relying on this project's cost
estimates for real budgeting.

## Setup

1. Copy `.env.example` to `.env` and add your Gemini API key
   (get one at https://aistudio.google.com/apikey).
2. Install dependencies: `uv sync --all-groups`

## Usage

Run the comparison:

```bash
uv run python main.py
```

Use your own document, and set a custom cache TTL (seconds):

```bash
uv run python main.py --doc /path/to/file.txt --ttl 120
```

### Example output

```
Loaded document: C:\Users\HP\Documents\prompt-caching-project\sample_doc.txt (8489 characters)
Running 6 questions against 3 caching modes...

Mode 1/3: No cache baseline...
Mode 2/3: Implicit cache (same calls, observing automatic cache hits)...
Mode 3/3: Explicit cache...

Mode              Calls  Prompt tok  Cached tok  Output tok  Think tok  Avg latency  Est. cost
----------------------------------------------------------------------------------------------
No cache              6        9881        1010         303       1816        2.62s $ 0.007989
Implicit cache        6        9881        2020         299       1718        2.61s $ 0.007461
Explicit cache        6        9887        9756         298       1785        2.60s $ 0.005539

Explicit cache overhead (not included in the table's Est. cost column):
  Cache creation  (1626 tokens, billed at input rate): $0.000488
  Cache storage   (alive 15.6s): $0.000007
  Per-question usage (from table above): $0.005539
  Total explicit cache cost: $0.006034

Done.
```

Either the "No cache" or "Implicit cache" row can show nonzero cached
tokens on any given run — sometimes both do (as in the example above),
sometimes neither does, since it depends on unpredictable server-side
caching behavior. Gemini's implicit caching can kick in on calls not
deliberately using an explicit cache, because both modes make the identical
underlying API call. That's expected, not a bug: it's exactly the behavior
this project is here to demonstrate.

You may also notice the Explicit cache row's "Prompt tok" total is a few
tokens higher than the No cache / Implicit cache rows. This is expected: the
explicit-cache document lives in its own cached `Content` turn, and each
question is sent as a separate new turn appended after it, whereas the other
two modes send the document and question together as one combined turn
(`contents=[doc_text, question]`). Two turns instead of one adds a small
amount of structural (role/turn-boundary) token overhead per call — a few
tokens total, not a caching bug. It's negligible for cost, since almost the
entire prompt in that row is billed at the discounted cached rate anyway.

Don't expect the Explicit cache row to consistently have the lowest "Avg
latency" — across repeated runs it's sometimes the fastest, sometimes the
slowest. Caching mainly saves the cost of re-processing the cached prefix,
not generation time: latency here is dominated by decoding the output and
thinking tokens (autoregressive generation, ~300 output + ~1,700-2,000
thinking tokens per call), which caching doesn't speed up. Skipping
re-encoding the cached prefix would matter more for latency with a much
larger cached document; at this sample document's size (~1,600 tokens) the
effect is small and easily swamped by normal network/server variance. Cost
savings, on the other hand, show up reliably every run.

The table's "Est. cost" column only covers the per-question generation
cost — it's deliberately an apples-to-apples number across all 3 rows.
Explicit caching has two more cost components that don't apply to the
other modes, printed separately right after the table instead of being
folded silently into the same number:

- **Cache creation** — the first time Google processes the document to
  build the cache, it's billed once at the standard input rate (not the
  discounted cached rate — that discount only applies to later calls that
  reference the cache).
- **Cache storage** — Google charges $1.00 per 1M cached tokens per hour
  just for the cache existing. `main.py` creates the cache, runs all 6
  questions, then deletes it immediately afterward, measuring the real
  elapsed time in between — so in this run the cache only existed for
  ~15 seconds and the storage fee is a tiny fraction of a cent. A cache
  kept alive much longer (or holding a much larger document) would see
  this cost become more significant.

Even adding creation + storage on top of the per-question cost, the
Explicit cache mode's true total (see "Total explicit cache cost" above)
is still cheaper than the No cache baseline in this example — the
discount on repeated cached-token usage outweighs the one-time creation
fee once you're asking more than a couple of questions against the same
document.

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

- [ ] `uv run python main.py` prints a 3-row comparison table with nonzero
      prompt tokens per row and a nonzero "Cached tok" value on the Explicit
      cache row.
