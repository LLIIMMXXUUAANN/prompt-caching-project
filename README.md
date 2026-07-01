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
