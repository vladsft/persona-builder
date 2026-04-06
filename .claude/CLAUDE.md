# Persona Builder — Agent Onboarding

## What this is

"Prea Mult Banciu" — an AI chatbot replicating Romanian TV commentator Radu Banciu's voice, built from YouTube transcript chunks + a hand-crafted worldview document. First deliverable of a broader "Persona Museum" platform vision.

## Architecture at a glance

```
User query → hybrid_retrieve() → [BM25 top-20 ∪ embedding top-20] → RRF merge → diversify → top_k×3 candidates
           → rerank() → cheap LLM picks top_k from candidates
           → build_augmented_user_message() → system prompt (worldview + persona rules, cached) + context + history
           → LLM stream → Streamlit UI
```

Retrieval gracefully degrades: if no `corpus_embeddings.npy` exists, it falls back to BM25-only. If no signal passes the score threshold, retrieval is skipped entirely and the worldview handles the query alone.

## Key files

- `src/persona_builder/retrieval.py` — all retrieval logic: BM25, embeddings, cosine similarity, RRF, score thresholds, diversification, LLM re-ranking, formatting
- `src/persona_builder/streamlit_app.py` — chat UI, calls `hybrid_retrieve()` + `rerank()`, manages conversation history compression
- `src/persona_builder/llm_client.py` — multi-provider LLM dispatch (Anthropic/OpenAI/Gemini) with Anthropic prompt caching
- `src/persona_builder/persona_prompt.py` — system prompt template, injects worldview from `data/worldview/banciu_worldview.md`
- `src/persona_builder/process_transcripts.py` — ingestion pipeline (yt-dlp → SRT parse → chunk → JSON)
- `src/persona_builder/paths.py` — all path constants; everything under `data/` is gitignored except `samples/` and `worldview/`

## Data layout

- `data/output/*.json` — processed episodes (35 files, chunks of ~600 words each)
- `data/output/corpus_embeddings.npy` — cached OpenAI embeddings (generated via `make embeddings`)
- `data/worldview/banciu_worldview.md` — Romanian-language worldview document (persona's soul)
- `data/input/banciu_videos.csv` — source video list

All data under `data/output/`, `data/temp/`, `data/input/banciu_videos.csv` is gitignored.

## Commands

| Command | What it does |
| --- | --- |
| `make install && make editable` | Set up runtime deps + editable install |
| `make test` | Run tests (10 passing). Preprocessing tests need `requirements-preprocess.txt` |
| `make app` | Launch Streamlit chat |
| `make embeddings` | Generate/cache corpus embeddings (requires `OPENAI_API_KEY`, ~$0.001) |
| `make process` | Full ingestion pipeline (fetch + process transcripts) |
| `make worldview` | Regenerate worldview synthesis |

## How retrieval works

1. `hybrid_retrieve()` in `retrieval.py` is the main entry point
2. BM25 scores the query against all chunks (Romanian accent-stripped tokenization)
3. If embeddings exist: embed query via OpenAI, compute cosine similarity, merge BM25 + embedding rankings via RRF (k=60)
4. Score threshold check: BM25 `min_score=2.0`, embedding cosine `0.25`. Both must fail for retrieval to be skipped. BM25-only mode skips when BM25 alone fails.
5. Episode diversification: max `ceil(top_k/2)` chunks per episode
6. Over-fetch `top_k * 3` candidates, then `rerank()` uses a cheap LLM call to pick the best `top_k`
7. Chunks truncated to 400 words at prompt injection time

## Things to watch out for

- BM25 scores on tiny corpora (e.g., in tests) are negative — always pass `min_score=-float("inf")` in unit tests to disable the threshold
- The `retrieve()` function still exists for backward compatibility but `hybrid_retrieve()` is what the app uses
- `OPENAI_API_KEY` is needed for two independent things: embeddings generation AND the OpenAI LLM provider. Embeddings always use OpenAI regardless of `LLM_PROVIDER`.
- Worldview doc and persona prompt are in Romanian. The entire system is Romanian-first.
- `process_transcripts.py` imports `yt_dlp` at module level — its tests fail without `requirements-preprocess.txt` installed. Run retrieval tests separately: `pytest tests/test_retrieval.py`

## Roadmap (see PROJECT_STATUS.md for full details)

Completed: score threshold gating, hybrid retrieval with RRF, smaller chunks (600 words), LLM re-ranking.

Next up (in priority order):
1. Pre-compressed chunks at index time
2. Topic metadata enrichment

Long-term: generalize pipeline into multi-persona "Persona Museum" platform.

## Environment

Keys via `.env`: `ANTHROPIC_API_KEY` (required), `OPENAI_API_KEY` (required for embeddings), `GEMINI_API_KEY` (optional). `LLM_PROVIDER` defaults to `anthropic`.
