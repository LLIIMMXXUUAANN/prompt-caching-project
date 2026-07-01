# Gemini Caching Comparison CLI — Design

## Purpose

A small Python CLI to learn Gemini 2.5 Flash prompt caching by doing. It runs
the same batch of questions against the same document three ways — no
caching, implicit (automatic) caching, and explicit (`CachedContent`)
caching — and prints a side-by-side comparison of tokens billed, estimated
cost, and latency. It then optionally drops into an interactive chat session
against the explicit cache, so the user can watch cache hits and TTL expiry
happen live.

## Non-goals

- Not a production tool or reusable library — it's a learning exercise.
- No automated test suite (see Testing section for why).
- No support for arbitrary file formats beyond plain text at first pass.
- No persistence of past runs/results between invocations.

## Background: the mechanics being demonstrated

Gemini 2.5 Flash has two distinct caching paths:

- **Implicit caching**: fully automatic. If a request's initial prefix
  (e.g. a repeated system prompt or document) matches a previous request,
  Google may serve the matching portion from cache and bill it at a
  discount. No code changes are required to get this — it's simply
  observed via `response.usage_metadata.cached_content_token_count` after
  the fact. There's no guarantee of a hit; it depends on recent traffic and
  server-side cache state.
- **Explicit caching**: the caller creates a `CachedContent` resource via
  `client.caches.create(...)` with a TTL, then references it by name
  (`config=types.GenerateContentConfig(cached_content=cache.name)`) in
  subsequent `generate_content` calls. This guarantees the cached tokens are
  reused (until the TTL expires) and is billed at a discounted per-token
  rate, plus a small storage cost while the cache is alive.
- Minimum cacheable size for explicit caching on 2.5 Flash is approximately
  1024 tokens — content smaller than that cannot be explicitly cached.

The project uses the current `google-genai` SDK (not the deprecated
`google-generativeai` package).

## Architecture

Flat, single-directory project — no package hierarchy needed for a project
this size:

```
prompt-caching-project/
├── main.py             # entry point: orchestrates the 3-way comparison + interactive tail
├── gemini_cache.py      # thin wrapper around google-genai: create/reuse explicit cache, generate with/without cache
├── pricing.py           # token -> cost math; hardcoded Gemini 2.5 Flash rates, clearly labeled with as-of date
├── sample_doc.txt        # bundled public-domain long text (~8-10k tokens), default content
├── questions.py           # hardcoded list of 5-6 questions about sample_doc.txt
├── .env.example            # documents GEMINI_API_KEY
├── .env                     # actual key (gitignored)
├── .gitignore
└── requirements.txt          # google-genai, python-dotenv
```

Each file has one job:
- `gemini_cache.py` only knows how to talk to the Gemini API (create cache,
  generate content with/without cache reference). It doesn't know about
  pricing or CLI concerns.
- `pricing.py` only knows how to turn token counts into dollar estimates.
  It doesn't call the API.
- `main.py` orchestrates: loads the doc, runs the three modes using
  `gemini_cache.py`, feeds results through `pricing.py`, prints tables, and
  runs the interactive tail.

## Data flow

1. Load document text — defaults to `sample_doc.txt`, overridable with
   `--doc <path>`.
2. Load the fixed question list from `questions.py`.
3. **Mode 1 — No-cache baseline**: for each question, call
   `generate_content` with `[full_doc_text, question]` sent fresh every
   time. Record `prompt_token_count`, `cached_content_token_count`
   (expected 0), wall-clock latency, and per-call estimated cost.
4. **Mode 2 — Implicit cache**: identical call pattern to Mode 1 (same
   doc + question, no code path differences), run immediately after Mode 1
   so the prefix is likely still warm in Google's automatic cache. Same
   metrics recorded — the only expected difference from Mode 1 is whatever
   `cached_content_token_count` comes back as. This is the point: nothing
   in the code changes between Mode 1 and Mode 2, only the observed
   server-side behavior.
5. **Mode 3 — Explicit cache**: call `client.caches.create(model=...,
   config=types.CreateCachedContentConfig(contents=[...], ttl='300s'))`
   once with the document as cached content. For each question, call
   `generate_content(contents=question, config=types.GenerateContentConfig(
   cached_content=cache.name))`. Record the same metrics, plus the cache's
   reported token count and expiry timestamp.
6. Print a comparison table: per-mode total tokens billed at full price vs.
   discounted cache price, total estimated cost, average latency.
7. **Interactive tail** (skipped with `--no-chat`): drop into a REPL that
   keeps using the Mode 3 explicit cache. Each turn prints tokens used /
   tokens served from cache / running cost. TTL is deliberately short
   (e.g. 120–300s) so a user chatting for a few minutes can observe the
   cache expire mid-session.

## Configuration

- `GEMINI_API_KEY` read from `.env` via `python-dotenv`.
- CLI flags: `--doc <path>` (override sample document), `--no-chat` (skip
  interactive tail), `--ttl <seconds>` (override explicit cache TTL,
  default 300s).

## Error handling

- Missing `GEMINI_API_KEY` → fail fast with a clear message pointing at
  `.env.example`, before any API call is attempted.
- Document below the explicit-caching minimum token threshold → warn and
  skip Mode 3 (and the interactive tail, since it depends on Mode 3's
  cache) rather than letting a raw API error surface.
- Explicit cache expired mid-interactive-session → catch the specific API
  error, tell the user the cache expired, offer to recreate it (or exit
  the chat cleanly).
- Any single question failing during Modes 1–3 (network/API error) →
  print which question failed and continue with the rest of that mode's
  questions rather than aborting the whole comparison run.

## Testing

This project's core value is exercising a live external API and observing
real billing/caching behavior — there is no meaningful unit under test that
doesn't involve a real network call to Gemini. Accordingly there is no
automated test suite. Verification is manual: run the script end-to-end
with a real API key and confirm:
- the comparison table shows explicit (and usually implicit) cache modes
  cheaper than the no-cache baseline,
- `cached_content_token_count` is nonzero in Modes 2 and 3,
- the interactive tail shows a cache hit on the first turn and, after the
  TTL elapses, a clear "cache expired" message instead of a crash.

## Pricing data

`pricing.py` hardcodes Gemini 2.5 Flash per-token rates (input, output,
cached-input, cache storage-per-hour) as constants with a comment noting
the date they were last verified and a link to Google's pricing page for
the user to confirm they're still current. This is a learning tool, not a
billing system — approximate, clearly-labeled figures are sufficient.
