# Project Status

Last updated: 2026-04-12

## Current Stage: Launch-ready — preparing for r/Romania public demo (~1 week)

What exists and works:

- Streamlit chat app with streaming responses
- BM25 retrieval over transcript chunks with Romanian-aware tokenization
- Episode diversification in retrieval (max top_k/2 chunks per episode)
- Worldview-grounded persona prompt — written in Romanian, culturally adapted (not translated)
- **Contrarian instinct** in system prompt — explicit instructions to resist consensus answers
- Multi-provider LLM abstraction (Anthropic / OpenAI / Gemini / DeepSeek)
- **A/B model testing**: random per-session assignment across 4 variants (Sonnet 4.6, Haiku 4.5, DeepSeek Chat, Gemini 2.5 Flash)
- Transcript ingestion pipeline: yt-dlp subtitle download → SRT cleanup → sentence-boundary chunking → JSON
- Corpus QA tooling (noise detection, suspect-start flagging)
- **Prompt caching**: Anthropic system prompt + conversation history prefix cached (10% cost after 1st message)
- Conversation history summarization (older exchanges compressed into a rolling summary)
- Chunk truncation at injection time (→ 400 words max in prompt)
- **Rate limiting**: IP-based (3 sessions/IP/24h), global daily cap (300), 8-message per-session hard cap
- **Kill switch**: `KILL_SWITCH=1` env var instantly disables the app
- **Content filter**: regex-based, blocks explicit violence/doxxing, tolerant of strong opinions. Flagged outputs logged.
- **Analytics**: per-session and per-message logging (model, topics, IP hash, fingerprint, drop-off point)
- **Post-session poll**: Persona Museum validation ("Ai vrea sa vorbesti si cu alte personaje AI?")
- **UI safety**: AI disclaimer banner, mobile-first CSS
- **Load tested**: 50 concurrent sessions, 80ms avg retrieval, rate limiting verified correct

## Numbers

- Source list: 37 videos in `data/input/banciu_videos.csv` (Jan 2025 → Mar 2026)
- Processed corpus: 35 episodes in `data/output/` (~1050 chunks)
- 1 episode fails: `-r3FcC9erqo` — no Romanian subtitles, needs ffmpeg for Whisper audio fallback
- 1 episode has minor French intro noise: `4Q78wT5SU5A`
- Tests: 3 retrieval tests passing
- Load test: 50 concurrent sessions pass (80ms avg, 159ms P95 retrieval)

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
│   ├── llm_client.py               # Multi-provider LLM dispatch (Anthropic/OpenAI/Gemini/DeepSeek) + prompt caching
│   ├── streamlit_app.py            # Chat app, A/B testing, rate limiting, analytics, content filter, poll
│   ├── persona_prompt.py           # System prompt with worldview + contrarian instinct
│   ├── retrieval.py                # BM25 index, retrieval, diversification, formatting
│   ├── fetch_videos.py             # yt-dlp video/subtitle fetching
│   ├── extract_worldview.py        # Worldview extraction logic
│   └── paths.py                    # Shared path constants
├── data/
│   ├── input/banciu_videos.csv     # Source video list (37 entries, verified dates)
│   ├── output/*.json               # Processed episode corpus (35 episodes)
│   ├── logs/                       # Analytics, A/B logs, poll results, flagged outputs (gitignored)
│   ├── temp/                       # Downloaded subtitle/audio scratch files
│   └── worldview/banciu_worldview.md  # Romanian worldview document
├── tests/
│   ├── test_retrieval.py           # Retrieval unit tests
│   └── load_test.py                # 50-session concurrent load test
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

Provide API keys via `.env` or Streamlit secrets. See `.env.example` for full reference.

Required for A/B testing:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...          # Also needed for embeddings
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...
```

Deployment controls (set on Streamlit Cloud):
```
DEPLOYMENT=web                 # Enables rate limiting + hides sources
KILL_SWITCH=0                  # Set to "1" to instantly disable
MAX_SESSIONS_PER_IP=3          # Per-IP 24h session limit
DAILY_SESSION_CAP=300          # Global daily session cap
```

Optional:
```
TOP_K=5
MAX_TOKENS=600
```

---

## Recent Changes (2026-04-12): Launch Readiness

Implemented all features needed for the r/Romania public demo:

- **A/B model testing**: 4 variants (Sonnet 4.6, Haiku 4.5, DeepSeek Chat, Gemini 2.5 Flash), random per-session assignment, logged to `data/logs/ab_sessions.jsonl`
- **Rate limiting**: IP-based (3/IP/24h), global daily cap (300), 8-message per-session. In-memory store via `st.cache_resource`, thread-safe.
- **Kill switch**: `KILL_SWITCH=1` env var
- **Contrarian instinct**: New system prompt section + worldview adjustments (Hagi de-canonized, Lucescu added)
- **Analytics**: per-message logging with keyword topic tags (fotbal/politica/personal/altele), IP hash, fingerprint
- **Post-session poll**: Persona Museum validation after 8th message
- **Content filter**: regex-based, blocks violence/doxxing, tolerant of strong opinions. Flagged outputs logged.
- **UI**: AI disclaimer banner, mobile-first CSS
- **Prompt caching**: system prompt + conversation history prefix cached (Anthropic)
- **DeepSeek provider**: added to llm_client via OpenAI-compatible API
- **Load test**: 50 concurrent sessions, 80ms avg / 159ms P95 retrieval, rate limiting and logging verified correct

### Manual steps remaining for launch
- Set $100 spending caps on Anthropic, DeepSeek, and Google API dashboards
- Add all 4 API keys + `DEPLOYMENT=web` to Streamlit Cloud secrets
- Test the deployed app end-to-end with all 4 providers

---

## Previous Changes (2026-03-31): Persona Quality & Voice Fidelity

After QA testing the AI against real Banciu knowledge, identified and fixed several persona issues:

### Prompt engineering fixes (persona_prompt.py)
- **Style marker overuse**: "Păi" started every sentence, "Aia-i povestea" appeared constantly. Changed instructions from "adesea" (which LLMs read as "always") to explicit variation rules with "nu la fiecare replică" and "maximum una per replică".
- **Monologue mode → dialogue mode**: Response structure section rewritten from TV-format ("3-5 paragrafe") to conversational ("adaptezi lungimea la situație", allow 2-3 sentence replies, allow turning questions back).
- **Anti-fabrication guardrail**: New "SUBIECTE PE CARE NU LE CUNOȘTI" section. The AI was inventing elaborate opinions on topics Banciu never discussed (e.g., detailed Spanish language preferences). Now instructed to say "Nu e domeniul meu" or "Ce mă interesează pe mine?" rather than fabricate.

### Worldview rewrite (banciu_worldview.md)
- **Football section completely rewritten**: Was framed through meritocracy ("foamea, ambiția, seriozitatea"). Now captures Banciu's actual romantic view — talent over hard work, artistry over discipline, Maradona as archetype. Added specific Hagi opinion (severe, not diplomatic).
- **New section: "Formarea prin lipsuri — imaginația ca valoare"**: Critical missing layer. Banciu grew up under communism with nothing, served in the Army in the '90s. His generation lived through imagination — imagining what's beyond borders. This explains his romanticism about the West, his contempt for comfortable mediocrity, his value of beauty/culture. Without this, the AI "gets the imitation right but misses the human part."
- **Strengthened simulation limits**: Added explicit instruction that not every topic deserves an elaborate opinion.

### Open design question: monologue vs dialogue
Banciu is famous for monologues — that's his format. But in a chat interface, wall-of-text monologues feel heavy. Current prompt defaults to TV-monologue with allowance for shorter replies on trivial questions. Needs user testing on r/Romania: do fans want the monologue experience or a more conversational Banciu?

### Anti-fabrication calibration (resolved)
First version: too permissive (fabricated detailed Spanish language preferences). Second version: too restrictive (refused to opine on Bitcoin, dismissed topics as "nu e raionul meu"). Current version: extrapolate from worldview on any topic, but don't invent specific facts. Banciu has opinions about everything — he just doesn't have specialist knowledge.

### Corpus expansion planned
- 7 football episodes (including Maradona death episode as anchor)
- 2 politics episodes
- 1 travel episode

### Still needed for persona quality
- **Transcript QA**: Name errors in subtitles (e.g., "Ionita" instead of "Ioanitoaia"). Need a QA pass + corrections mechanism that survives reprocessing (skip-existing mode + corrections.json layer).
- **More football episodes in corpus**: Maradona death episode particularly valuable for football philosophy.
- **More critical Romanian football data**: AI too diplomatic about Hagi and Romanian national team.

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

### 6. Topic-conditioned retrieval boost (MEDIUM priority, for V2)

**Problem**: Some episodes are canonical for specific topics (e.g., the Maradona death episode for football philosophy). But BM25/embeddings treat all chunks equally — a passing mention of football in a politics episode can outrank the definitive Maradona monologue if the lexical match is stronger.

**Solution**: Pre-compute 2-3 topic tags per episode (football, politics, culture, journalism, Romania). At retrieval time, detect the query topic and apply a score boost (e.g., 1.3×) to chunks from episodes tagged with that topic. Mark certain episodes as "anchor" episodes for specific topics — these get a higher boost (e.g., 1.5×).

**Impact**: Ensures the most relevant, high-signal episodes surface first for their core topics. Particularly valuable for football and other areas where Banciu has signature episodes that define his stance.

**Cost**: One-time tagging (can be automated with a cheap LLM call per episode). Per-query: trivial score multiplication.

### 7. Topic metadata enrichment (LOW priority, for V2)

**Solution**: Pre-compute key entities and emotional tone per chunk. Enables filtered retrieval ("give me chunks about football mentioning Steaua").

**Impact**: Most valuable for multi-turn conversations and for a future UI with topic browsing.

---

## Long-term Vision: Persona Museum

"Prea Mult Banciu" is the first deliverable of a broader **Persona Museum** — a platform for AI replicas of public figures built from their own public content.

### Phase 1: Banciu PoC (current — launching)
- Ship to r/Romania as a free demo (~1 week)
- A/B testing 4 models to compare persona quality
- Rate limiting + kill switch + content filter for safety
- Analytics + post-session poll for Persona Museum validation
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
