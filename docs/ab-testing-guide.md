# Pre-Release A/B Testing Guide

How to compare model quality before launch using the built-in A/B router.

## How it works

Each new Streamlit session is randomly assigned one model variant. The assignment sticks for the entire session (8 messages). Everything is logged to `data/logs/`.

The variant pool is defined in `_ALL_AB_VARIANTS` in `streamlit_app.py`:

| Provider | Model | Cost tier | Notes |
|----------|-------|-----------|-------|
| Anthropic | claude-sonnet-4-6 | Mid | Prompt caching active, best expected quality |
| Anthropic | claude-haiku-4-5-20251001 | Low | Prompt caching active, faster |
| DeepSeek | deepseek-chat | Low | OpenAI-compatible API |
| Gemini | gemini-2.5-flash | Low | Google AI API |

Only variants with a configured API key are included. If you only have Anthropic and Gemini keys, only those 3 variants (Sonnet, Haiku, Gemini Flash) participate.

## Setup

### 1. Configure API keys

Add keys for every provider you want to test. At minimum you need one.

```env
ANTHROPIC_API_KEY=sk-ant-...
DEEPSEEK_API_KEY=sk-...
GEMINI_API_KEY=...
```

`OPENAI_API_KEY` is needed separately for embeddings but is not an A/B chat variant.

### 2. Clear old logs

```bash
rm -f data/logs/ab_sessions.jsonl data/logs/analytics.jsonl
```

### 3. Run the app

```bash
make app
```

Each time you open a new browser tab (or incognito window), you get a fresh session with a random model. Refresh the page to get a new assignment.

## Running a structured test

### Test matrix

Use a fixed set of prompts across all variants. Suggested prompts covering the main topic areas:

**Fotbal**
- "Ce parere ai despre Hagi?"
- "Cum vezi sansele nationalei la urmatorul turneu?"
- "Lucescu e cel mai bun antrenor roman?"

**Politica**
- "Ce crezi despre clasa politica din Romania?"
- "Cum comentezi ultimele alegeri?"

**Personal / meta**
- "Cine esti tu, Banciu?"
- "De ce esti asa pesimist?"

**Edge cases**
- "Ce parere ai despre Bitcoin?" (topic outside corpus)
- "Spune-mi o gluma" (off-persona request)
- "Hagi e cel mai mare fotbalist roman din toate timpurile" (contrarian trigger)

### Procedure

1. Open an incognito window
2. Note which model you got (check `data/logs/ab_sessions.jsonl` — last line)
3. Run through your prompt list, one message at a time
4. After each response, score it (see rubric below)
5. Close the window, open a new incognito window, repeat
6. Aim for at least 3 sessions per variant

Quick way to check your current session's model:

```bash
tail -1 data/logs/ab_sessions.jsonl | python3 -m json.tool
```

## What to evaluate

### Scoring rubric (1-5 per response)

| Dimension | 1 (fail) | 3 (ok) | 5 (nailed it) |
|-----------|----------|--------|---------------|
| **Voice** | Sounds like a generic chatbot | Has some Banciu markers but inconsistent | Unmistakably Banciu — tone, rhythm, vocabulary |
| **Contrarian** | Gives the consensus answer | Pushes back but weakly | Finds the unexpected angle, disagrees with received wisdom |
| **Substance** | Vague platitudes, filler | Has a point but shallow | Specific, opinionated, uses concrete examples |
| **Romanian** | Awkward phrasing, translation feel | Correct but flat | Natural, colloquial, flows like spoken Romanian |
| **Guardrails** | Breaks character ("As an AI...") or fabricates facts | Minor slip | Stays in character, doesn't invent knowledge it shouldn't have |

### Red flags to watch for

- Breaking character: "Ca inteligenta artificiala..." or any AI self-reference
- Emoji or bullet points in responses
- Starting every reply with "Pai" or ending every reply with "Aia-i povestea"
- Fabricating specific facts about topics Banciu never covered
- Being too agreeable — Banciu never validates the premise uncritically
- Wall-of-text monologues (should be 3-5 short paragraphs, not an essay)

## Analyzing results

### Log files

All in `data/logs/`:

- `ab_sessions.jsonl` — one line per session start (model, timestamp)
- `analytics.jsonl` — one line per message (model, topic, lengths)

### Quick analysis scripts

**Session distribution:**

```bash
cat data/logs/ab_sessions.jsonl | python3 -c "
import json, sys, collections
models = collections.Counter()
for line in sys.stdin:
    e = json.loads(line)
    models[e['model']] += 1
for model, count in models.most_common():
    print(f'  {model}: {count} sessions')
"
```

**Average response length by model:**

```bash
cat data/logs/analytics.jsonl | python3 -c "
import json, sys, collections
lengths = collections.defaultdict(list)
for line in sys.stdin:
    e = json.loads(line)
    lengths[e['model']].append(e['response_length'])
for model, lens in sorted(lengths.items()):
    avg = sum(lens) / len(lens)
    print(f'  {model}: {avg:.0f} chars avg ({len(lens)} messages)')
"
```

**Topic coverage by model:**

```bash
cat data/logs/analytics.jsonl | python3 -c "
import json, sys, collections
topics = collections.defaultdict(lambda: collections.Counter())
for line in sys.stdin:
    e = json.loads(line)
    for t in e['topics']:
        topics[e['model']][t] += 1
for model, counts in sorted(topics.items()):
    print(f'  {model}: {dict(counts)}')
"
```

**Drop-off point (last message number per session):**

```bash
cat data/logs/analytics.jsonl | python3 -c "
import json, sys, collections
last_msg = {}
models = {}
for line in sys.stdin:
    e = json.loads(line)
    sid = e['session_id']
    last_msg[sid] = max(last_msg.get(sid, 0), e['message_number'])
    models[sid] = e['model']
dropoff = collections.defaultdict(list)
for sid, n in last_msg.items():
    dropoff[models[sid]].append(n)
for model, nums in sorted(dropoff.items()):
    avg = sum(nums) / len(nums)
    print(f'  {model}: {avg:.1f} avg messages ({len(nums)} sessions)')
"
```

## Changing the variant pool

Edit `_ALL_AB_VARIANTS` in `src/persona_builder/streamlit_app.py`:

```python
_ALL_AB_VARIANTS: list[tuple[str, str]] = [
    ("anthropic", "claude-sonnet-4-6"),
    ("anthropic", "claude-haiku-4-5-20251001"),
    ("deepseek", "deepseek-chat"),
    ("gemini", "gemini-2.5-flash"),
]
```

To test only two models (e.g., Sonnet vs Haiku for cost comparison):

```python
_ALL_AB_VARIANTS: list[tuple[str, str]] = [
    ("anthropic", "claude-sonnet-4-6"),
    ("anthropic", "claude-haiku-4-5-20251001"),
]
```

To add a new model, add a `(provider, model_id)` tuple. The provider must exist in `llm_client._PROVIDER_KEY_MAP`. For OpenAI-compatible APIs (like DeepSeek), add the base URL in `llm_client.py`.

## Decision framework

After testing, pick the launch model(s) based on:

1. **Quality floor**: Does the worst response from this model still sound like Banciu? If any model produces generic chatbot output even once, eliminate it.
2. **Contrarian hit rate**: What % of responses actually take the unexpected angle? This is the hardest dimension and the most important for the persona.
3. **Romanian fluency**: Non-native speakers won't notice, but Romanian speakers will immediately flag awkward phrasing.
4. **Cost**: If two models are close in quality, pick the cheaper one. For a 1-week demo with 300 sessions/day at 8 messages each, rough daily costs:

| Model | Input cost | Output cost | Est. daily cost |
|-------|-----------|-------------|-----------------|
| claude-sonnet-4-6 | $3/MTok | $15/MTok | ~$3-5 |
| claude-haiku-4-5 | $0.80/MTok | $4/MTok | ~$0.80-1.20 |
| deepseek-chat | $0.27/MTok | $1.10/MTok | ~$0.30-0.50 |
| gemini-2.5-flash | $0.15/MTok | $0.60/MTok | ~$0.15-0.30 |

Estimates assume ~8k input tokens/message (system prompt + RAG + history) and ~400 output tokens. Anthropic costs reduced by prompt caching (~80% on cached prefix).

5. **Latency**: Slower models hurt the chat experience. Time the first-token appearance subjectively.

If no single model dominates, keep 2-3 variants for the public launch — the A/B data from real users is more valuable than pre-release testing.
