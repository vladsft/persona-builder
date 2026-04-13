# Prea Mult Banciu

AI chatbot that responds in Radu Banciu's voice — built from his YouTube episode transcripts using RAG and a hand-crafted worldview document.

First deliverable of the **Persona Museum** vision (see [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for roadmap).

## How it works

1. **Corpus**: ~35 YouTube episodes → subtitle extraction → sentence-boundary chunking → JSON
2. **Worldview**: A hand-written Romanian document capturing Banciu's beliefs, values, contradictions, and rhetorical patterns — injected into every system prompt
3. **Retrieval**: BM25 lexical search over transcript chunks with Romanian-aware tokenization and episode diversification
4. **Generation**: System prompt (persona + worldview + contrarian instinct + style rules) + retrieved chunks + user query → streamed LLM response
5. **Optimization**: Anthropic prompt caching (system prompt + conversation history prefix at 10% cost after 1st message) + conversation history summarization (older turns compressed)

## Quickstart

```bash
make install
make editable
make test
make app
```

## Environment

Copy `.env.example` to `.env` and fill in your keys:

```
ANTHROPIC_API_KEY=sk-ant-...     # Required (A/B testing + prompt caching)
OPENAI_API_KEY=sk-...            # Required (embeddings)
DEEPSEEK_API_KEY=sk-...          # Required (A/B testing: deepseek-chat)
GEMINI_API_KEY=...               # Required (A/B testing: gemini-2.5-flash)
```

Deployment controls (set on Streamlit Cloud):
```
DEPLOYMENT=web                   # Enables rate limiting, hides sources
KILL_SWITCH=0                    # Set to "1" to instantly disable
MAX_SESSIONS_PER_IP=3            # Per-IP session limit (24h window)
DAILY_SESSION_CAP=300            # Global daily session cap
```

Optional tuning:
```
TOP_K=5                          # Chunks to retrieve per query
MAX_TOKENS=600                   # Max LLM output tokens
```

## A/B Model Testing

Each new session is randomly assigned one of four model variants:

| Provider | Model | Notes |
|----------|-------|-------|
| Anthropic | claude-sonnet-4-6 | Prompt caching active |
| Anthropic | claude-haiku-4-5-20251001 | Prompt caching active, cheaper |
| DeepSeek | deepseek-chat | OpenAI-compatible API |
| Gemini | gemini-2.5-flash | Google AI API |

Assignments logged to `data/logs/ab_sessions.jsonl`.

## Rate Limiting & Safety (web deployment)

- **Per-IP**: max 3 sessions per IP per 24h (configurable)
- **Global daily cap**: 300 sessions/day (configurable)
- **Per-session**: 8 messages hard cap
- **Kill switch**: `KILL_SWITCH=1` instantly disables the app
- **Content filter**: Blocks explicit violence, fabricated criminal accusations, doxxing. Tolerant of strong opinions and public figure criticism (Banciu's style).
- **Flagged outputs**: Logged to `data/logs/flagged_outputs.jsonl` for manual review

When daily cap is hit: "Banciu s-a dus la culcare, revino mâine."

## Analytics

Per-session and per-message events logged to `data/logs/`:

| File | Contents |
|------|----------|
| `ab_sessions.jsonl` | Session starts: model assignment, IP hash, fingerprint |
| `analytics.jsonl` | Messages: topic tags, response length, message number |
| `poll_results.jsonl` | Post-session poll: Persona Museum interest signal |
| `flagged_outputs.jsonl` | Blocked responses for manual review |

Topics auto-tagged via keyword matching: fotbal / politica / personal / altele.

## Post-Session Poll

After the 8th message, users see:
> "Ai vrea sa vorbesti si cu alte personaje AI?"
> Mircea Badea / CTP / Mircea Lucescu / Nu

Results logged separately — key signal for Persona Museum validation.

## Repository Layout

```text
persona-builder/
├── app.py                           # Streamlit entrypoint
├── fetch_banciu_videos.py           # YouTube video discovery CLI
├── process_banciu_transcripts.py    # SRT → chunked JSON CLI
├── extract_worldview.py             # Worldview extraction CLI
├── src/persona_builder/
│   ├── llm_client.py                # Multi-provider LLM dispatch + prompt caching
│   ├── streamlit_app.py             # Chat app, A/B testing, rate limits, analytics
│   ├── persona_prompt.py            # System prompt with worldview + contrarian instinct
│   ├── retrieval.py                 # BM25 index, retrieval, diversification
│   ├── fetch_videos.py              # yt-dlp video/subtitle fetching
│   ├── extract_worldview.py         # Two-pass worldview extraction
│   └── paths.py                     # Shared path constants
├── data/
│   ├── input/banciu_videos.csv      # Source video list
│   ├── output/*.json                # Processed episode corpus
│   ├── logs/                        # Analytics, A/B logs, flagged outputs (gitignored)
│   ├── temp/                        # Subtitle/audio scratch files
│   └── worldview/banciu_worldview.md
├── tests/
│   ├── test_retrieval.py            # Retrieval unit tests
│   └── load_test.py                 # 50-session concurrent load test
├── Makefile
├── requirements.txt                 # Runtime deps
└── requirements-preprocess.txt      # Preprocessing deps
```

## Pipeline Commands

Fetch or refresh the source video list:
```bash
python fetch_banciu_videos.py --use-default-dates
```

Process transcripts into the local corpus:
```bash
python process_banciu_transcripts.py
```

Run corpus QA:
```bash
python process_banciu_transcripts.py --qa-only
```

Regenerate worldview synthesis:
```bash
python extract_worldview.py
```

Run load test:
```bash
python tests/load_test.py
```

## Project Status

See [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) for current status, RAG improvement roadmap, and long-term Persona Museum vision.
