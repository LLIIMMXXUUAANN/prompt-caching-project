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
No cache              6        9881        2020         302       1883        3.00s $ 0.007881
Implicit cache        6        9881        1010         301       1868        2.68s $ 0.008114
Explicit cache        6        9887        9756         304       1731        2.84s $ 0.005419

Explicit cache deleted. Done.
```

Note the "No cache" row can still show nonzero cached tokens (as above) — Gemini's
implicit caching can kick in even on calls not deliberately using an explicit
cache, since both "No cache" and "Implicit cache" modes make the identical
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
