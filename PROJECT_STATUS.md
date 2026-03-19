# Project Status

Last updated: 2026-03-19

## Current Stage: Private MVP — ready for local QA, not yet deployed

What exists and works:

- Streamlit chat app with streaming responses
- BM25 retrieval over ~1200-word transcript chunks with Romanian-aware tokenization
- Episode diversification in retrieval (max top_k/2 chunks per episode)
- Worldview-grounded persona prompt — written in Romanian, culturally adapted (not translated)
- Multi-provider LLM abstraction (Anthropic / OpenAI / Gemini) with per-provider model defaults
- Transcript ingestion pipeline: yt-dlp subtitle download → SRT cleanup → sentence-boundary chunking → JSON
- Corpus QA tooling (noise detection, suspect-start flagging)
- Anthropic prompt caching (system prompt billed at 10% after first message in session)
- Conversation history summarization (older exchanges compressed into a rolling summary to cap token growth)
- Chunk truncation at injection time (1200 → 400 words max in prompt)

## Numbers

- Source list: 37 videos in `data/input/banciu_videos.csv` (Jan 2025 → Mar 2026)
- Processed corpus: 35 episodes in `data/output/` (~400+ chunks)
- 1 episode fails: `-r3FcC9erqo` — no Romanian subtitles, needs ffmpeg for Whisper audio fallback
- 1 episode has minor French intro noise: `4Q78wT5SU5A`
- Tests: 6/6 passing

## Token Budget (per message, Anthropic)

| Component | Tokens | Notes |
|-----------|--------|-------|
| System prompt (worldview + style) | ~4,200 | Cached after 1st message (90% cost reduction) |
| Retrieved chunks (5 × truncated) | ~3,500 | Was ~7,750 before truncation |
| Conversation history | capped | Summarized after 3 exchanges |
| User message | ~100 | |
| Output | ~600 | |

First message: ~8,400 input. Subsequent: ~5,000 effective cost (caching). History no longer grows unboundedly.

## Repository Layout

```text
persona-builder/
├── app.py                          # Streamlit entrypoint
├── fetch_banciu_videos.py          # YouTube video discovery CLI
├── process_banciu_transcripts.py   # SRT → chunked JSON CLI
├── extract_worldview.py            # Two-pass worldview extraction CLI
├── src/persona_builder/
│   ├── llm_client.py               # Multi-provider LLM dispatch + Anthropic prompt caching
│   ├── streamlit_app.py            # Chat app with RAG + history summarization
│   ├── persona_prompt.py           # System prompt template with worldview injection
│   ├── retrieval.py                # BM25 index, retrieval, diversification, formatting
│   ├── fetch_videos.py             # yt-dlp video/subtitle fetching
│   ├── extract_worldview.py        # Worldview extraction logic
│   └── paths.py                    # Shared path constants
├── data/
│   ├── input/banciu_videos.csv     # Source video list (37 entries, verified dates)
│   ├── output/*.json               # Processed episode corpus (35 episodes)
│   ├── temp/                       # Downloaded subtitle/audio scratch files
│   └── worldview/banciu_worldview.md  # Romanian worldview document
├── tests/                          # Unit tests (6 passing)
├── Makefile
├── pyproject.toml
├── requirements.txt                # Runtime deps (anthropic, openai, google-genai, rank-bm25, streamlit)
└── requirements-preprocess.txt     # Preprocessing-only deps (yt-dlp, whisper, etc.)
```

## Quickstart

```bash
make install
make editable
make test
make app
```

## Environment

Provide API keys via `.env` or Streamlit secrets:

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...        # optional, for OpenAI provider
GEMINI_API_KEY=...        # optional, for Gemini provider
LLM_PROVIDER=anthropic    # or "openai" or "gemini"
MODEL=claude-sonnet-4-6   # optional, auto-detected per provider
TOP_K=5
MAX_TOKENS=600
```

---

## Next Steps: RAG Improvements (prioritized)

The current retrieval is functional but naive — BM25 lexical-only, large chunks, no quality gating. These improvements are ordered by impact on the Banciu use case.

### 1. Score threshold — skip bad retrieval (HIGH priority, SMALL effort)

**Problem**: Every query triggers RAG, even when nothing relevant exists in the corpus. Generic or identity questions ("Cine ești?", "Ce crezi despre viață?") pull in random high-frequency chunks that add noise and confuse the persona.

**Solution**: Check the top BM25 score against a minimum threshold. If nothing matched well, return zero chunks and let the worldview + persona prompt handle it alone.

**Impact**: Prevents the model from getting polluted with irrelevant context. Saves ~3,500 tokens on those queries. Estimated 30-50% of casual conversation queries don't need retrieval at all.

**Cost**: Zero — just a threshold check.

### 2. Hybrid retrieval — BM25 + embeddings with reciprocal rank fusion (HIGH priority, MEDIUM effort)

**Problem**: BM25 matches words, not meaning. "Ce crezi despre sistemul educațional?" won't match a chunk about "școală, profesori, analfabeți funcțional" because the words don't overlap. This is the core quality gap.

**Solution**: Embed all chunks once at build time (OpenAI `text-embedding-3-small`, multilingual, $0.02/1M tokens). At query time, BM25 returns top-20, embedding cosine similarity returns top-20, merge via reciprocal rank fusion. BM25 catches exact matches ("Iohannis", "Steaua"), embeddings catch semantic matches ("corupție" ↔ "hoție").

**Impact**: Significantly better retrieval precision, especially for Romanian colloquial queries against Banciu's specific vocabulary. Enables confidently reducing top_k from 5 to 3 (fewer but better chunks = fewer tokens + better quality).

**Cost**: One-time embedding: ~$0.001 for the entire corpus. Per query: one embedding call ~$0.00002. Storage: numpy array on disk, loaded at app start alongside BM25 index.

### 3. Smaller, topic-segmented chunks (~400 words) (MEDIUM priority, MEDIUM effort)

**Problem**: Current chunks are ~1200 words. A single chunk can cover 3-4 topics because Banciu's monologues ramble. Retrieved chunks contain mostly noise — maybe 2 paragraphs are relevant out of 1200 words.

**Solution**: Re-chunk transcripts at ~400 words with sentence-boundary awareness. Ideally detect topic shifts and break there. This creates ~3-4x more chunks but each is focused on one topic.

**Impact**: Combined with hybrid retrieval, you get surgical precision — 3 chunks of 400 words that are all relevant, instead of 5 chunks of 1200 words where half is noise. The model gets cleaner signal and produces more authentic Banciu responses.

**Cost**: Re-processing the corpus (one-time). More chunks in memory but less context injected per query.

### 4. Re-ranking stage (MEDIUM priority, SMALL effort)

**Problem**: Taking the top-k directly from BM25/hybrid is a recall-optimized approach. The difference between rank #1 and rank #5 can be "exactly this topic" vs. "vaguely related."

**Solution**: Retrieve top-15, then re-rank with Cohere Rerank API ($0.002/query) or a cheap LLM call. Take the top-3 after re-ranking.

**Impact**: Upgrades from "good enough" to "surgical" chunk selection. Most valuable when multiple episodes touch similar topics.

### 5. Pre-compressed chunks at index time (LOW priority, MEDIUM effort)

**Solution**: For each chunk, use a cheap model to extract key claims, opinions, and entities into ~150 words. Store both full text (for source display) and compressed version (for prompt injection).

**Impact**: Each chunk goes from ~500 tokens (after truncation) to ~200 tokens. 5 compressed chunks ≈ 1,000 tokens vs. ~3,500 currently.

### 6. Topic metadata enrichment (LOW priority, for V2)

**Solution**: Pre-compute 2-3 topic tags, key entities, and emotional tone per chunk. Enables filtered retrieval ("give me chunks about football mentioning Steaua").

**Impact**: Most valuable for multi-turn conversations and for a future UI with topic browsing.

---

## Long-term Vision: Persona Museum

"Prea Mult Banciu" is the first deliverable of a broader **Persona Museum** — a platform for AI replicas of public figures built from their own public content.

### Phase 1: Banciu PoC (current)
- Ship to r/Romania as a free demo
- Validate that RAG + worldview + persona prompt can produce convincing voice replication
- Test product-market fit: do people enjoy talking to it? Do they come back?
- Gather feedback on voice fidelity, topic coverage, failure modes

### Phase 2: Banciu polished product
- Implement hybrid retrieval + re-ranking (steps 2-4 above)
- Expand corpus to 50-100 episodes for broader topic coverage
- Add conversation memory (user preferences, topics discussed)
- Deploy on Streamlit Community Cloud (free hosting)
- Consider custom domain

### Phase 3: Platform generalization
- Extract the persona-building pipeline into a reusable framework
- Pipeline: YouTube channel → subtitle download → chunking → embedding → worldview extraction → persona prompt generation → chat app
- Second persona candidate: pick another Romanian public figure with a distinctive voice and abundant YouTube content
- Validate that the pipeline generalizes — does it work for someone who isn't Banciu?

### Phase 4: Persona Museum platform
- Multi-persona deployment: users pick who to talk to
- Shared infrastructure: one retrieval/LLM backend, multiple persona configs
- User accounts, conversation history, favorites
- Potential monetization: freemium (N free messages/day), premium for unlimited or special personas
- Community submissions: let users propose public figures, vote on who gets built next

### Open questions for the vision
- Legal: what are the boundaries of replicating a living public figure's voice? (Non-commercial fan project for now, but matters at scale)
- Quality bar: how do you measure "good enough" voice replication? Manual QA? User ratings? A/B tests?
- Corpus requirements: what's the minimum content needed to build a convincing persona? (Hypothesis: ~30 episodes + a good worldview doc)
- Monetization timing: when does it make sense to charge? After 3 personas? After 1000 users?
