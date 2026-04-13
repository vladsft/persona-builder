# Persona Builder — Agent Onboarding

## What this is

"Prea Mult Banciu" — an AI chatbot replicating Romanian TV commentator Radu Banciu's voice, built from YouTube transcript chunks + a hand-crafted worldview document. First deliverable of a broader "Persona Museum" platform vision.

## Architecture at a glance

```
User opens session → IP rate check → A/B model assignment (random from 4 variants)
User query → retrieve() → BM25 top-k with diversification
           → build_augmented_user_message() → system prompt (worldview + contrarian instinct + persona rules, cached) + context + history
           → LLM stream (via assigned provider) → content filter → Streamlit UI
           → analytics log (topic tags, message count)
After 8th message → post-session poll (Persona Museum validation)
```

Prompt caching (Anthropic only): system prompt + conversation history prefix cached via `cache_control` breakpoints.

## Key files

- `src/persona_builder/retrieval.py` — BM25 retrieval, diversification, formatting, chunk truncation
- `src/persona_builder/streamlit_app.py` — chat UI, A/B model router, rate limiting (IP + global + per-session), analytics logging, content filter, post-session poll
- `src/persona_builder/llm_client.py` — multi-provider LLM dispatch (Anthropic/OpenAI/Gemini/DeepSeek) with Anthropic prompt caching
- `src/persona_builder/persona_prompt.py` — system prompt template with worldview injection and contrarian instinct section
- `src/persona_builder/process_transcripts.py` — ingestion pipeline (yt-dlp → SRT parse → chunk → JSON)
- `src/persona_builder/paths.py` — all path constants; everything under `data/` is gitignored except `samples/` and `worldview/`

## Data layout

- `data/output/*.json` — processed episodes (35 files, chunks of ~600 words each)
- `data/worldview/banciu_worldview.md` — Romanian-language worldview document (persona's soul)
- `data/input/banciu_videos.csv` — source video list
- `data/logs/` — analytics, A/B session logs, poll results, flagged outputs (gitignored)

All data under `data/output/`, `data/temp/`, `data/input/banciu_videos.csv`, `data/logs/` is gitignored.

## Commands

| Command | What it does |
| --- | --- |
| `make install && make editable` | Set up runtime deps + editable install |
| `make test` | Run tests. Preprocessing tests need `requirements-preprocess.txt` |
| `make app` | Launch Streamlit chat |
| `make process` | Full ingestion pipeline (fetch + process transcripts) |
| `make worldview` | Regenerate worldview synthesis |
| `python tests/load_test.py` | 50-session concurrent load test |

## A/B model testing

Each new session is randomly assigned one of 4 variants defined in `AB_VARIANTS` in `streamlit_app.py`:
- `("anthropic", "claude-sonnet-4-6")`
- `("anthropic", "claude-haiku-4-5-20251001")`
- `("deepseek", "deepseek-chat")`
- `("gemini", "gemini-2.5-flash")`

The `llm_client.stream()` and `llm_client.create()` accept an explicit `provider` parameter. The old `LLM_PROVIDER` env var still works as fallback for backward compatibility (e.g., `extract_worldview.py`).

## Rate limiting & safety

Three layers, all gated by `DEPLOYMENT=web`:
1. **IP-based**: max `MAX_SESSIONS_PER_IP` (default 3) new sessions per IP per 24h
2. **Global daily cap**: max `DAILY_SESSION_CAP` (default 300) sessions/day
3. **Per-session**: 8 messages hard cap (`RATE_LIMIT_MESSAGES`)

Kill switch: set `KILL_SWITCH=1` to instantly disable the app.

Content filter: regex-based, blocks explicit violence calls, fabricated criminal accusations, doxxing. Tolerant of strong opinions. Flagged outputs logged to `data/logs/flagged_outputs.jsonl`.

## Analytics

Logged to `data/logs/*.jsonl`:
- `ab_sessions.jsonl` — session start events (model, IP hash, fingerprint)
- `analytics.jsonl` — per-message events (topic tags, response length)
- `poll_results.jsonl` — post-session poll choices
- `flagged_outputs.jsonl` — blocked content for review

## Things to watch out for

- BM25 scores on tiny corpora (e.g., in tests) are negative — always pass `min_score=-float("inf")` in unit tests to disable the threshold
- `OPENAI_API_KEY` is needed for embeddings generation. Embeddings always use OpenAI regardless of the A/B-assigned provider.
- Worldview doc and persona prompt are in Romanian. The entire system is Romanian-first.
- `process_transcripts.py` imports `yt_dlp` at module level — its tests fail without `requirements-preprocess.txt` installed. Run retrieval tests separately: `pytest tests/test_retrieval.py`
- Rate limit store is in-memory (`st.cache_resource`). Resets on deploy/restart. Acceptable for short demo.

## Roadmap (see docs/PROJECT_STATUS.md for full details)

Completed: score threshold gating, smaller chunks (600 words), A/B model testing, rate limiting, analytics, content filter, contrarian instinct, post-session poll, prompt caching.

Next up (in priority order):
1. Pre-compressed chunks at index time
2. Topic metadata enrichment

Long-term: generalize pipeline into multi-persona "Persona Museum" platform.

## Environment

Keys via `.env` or Streamlit secrets:
- `ANTHROPIC_API_KEY` (required for A/B variant)
- `OPENAI_API_KEY` (required for embeddings)
- `DEEPSEEK_API_KEY` (required for A/B variant)
- `GEMINI_API_KEY` (required for A/B variant)
- `DEPLOYMENT=web` (enables rate limiting on Streamlit Cloud)
- `KILL_SWITCH=0` (set to "1" to disable app)
- `MAX_SESSIONS_PER_IP=3`, `DAILY_SESSION_CAP=300` (rate limit tuning)
