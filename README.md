# Prea Mult Banciu

AI chatbot that responds in Radu Banciu's voice — built from his YouTube episode transcripts using RAG and a hand-crafted worldview document.

First deliverable of the **Persona Museum** vision (see [PROJECT_STATUS.md](PROJECT_STATUS.md) for roadmap).

## How it works

1. **Corpus**: ~35 YouTube episodes → subtitle extraction → sentence-boundary chunking → JSON
2. **Worldview**: A hand-written Romanian document capturing Banciu's beliefs, values, contradictions, and rhetorical patterns — injected into every system prompt
3. **Retrieval**: BM25 lexical search over transcript chunks with Romanian-aware tokenization and episode diversification
4. **Generation**: System prompt (persona + worldview + style rules) + retrieved chunks + user query → streamed LLM response
5. **Optimization**: Anthropic prompt caching (system prompt at 10% cost after 1st message) + conversation history summarization (older turns compressed)

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
LLM_PROVIDER=anthropic    # or "openai" or "gemini"
```

Optional:
```
OPENAI_API_KEY=...
GEMINI_API_KEY=...
MODEL=claude-sonnet-4-6
TOP_K=5
MAX_TOKENS=600
```

## Repository Layout

```text
persona-builder/
├── app.py                           # Streamlit entrypoint
├── fetch_banciu_videos.py           # YouTube video discovery CLI
├── process_banciu_transcripts.py    # SRT → chunked JSON CLI
├── extract_worldview.py             # Worldview extraction CLI
├── src/persona_builder/
│   ├── llm_client.py                # Multi-provider LLM dispatch + prompt caching
│   ├── streamlit_app.py             # Chat app with RAG + history summarization
│   ├── persona_prompt.py            # System prompt with worldview injection
│   ├── retrieval.py                 # BM25 index, retrieval, diversification
│   ├── fetch_videos.py              # yt-dlp video/subtitle fetching
│   ├── extract_worldview.py         # Two-pass worldview extraction
│   └── paths.py                     # Shared path constants
├── data/
│   ├── input/banciu_videos.csv      # Source video list
│   ├── output/*.json                # Processed episode corpus
│   ├── temp/                        # Subtitle/audio scratch files
│   └── worldview/banciu_worldview.md
├── tests/
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

## Multi-provider Support

The app supports Anthropic, OpenAI, and Gemini via a unified LLM abstraction. Set `LLM_PROVIDER` to switch. Each provider has sensible model defaults:

| Provider | Default model |
|----------|--------------|
| anthropic | claude-haiku-4-5-20251001 |
| openai | gpt-4.1-mini |
| gemini | gemini-2.5-flash |

## Project Status

See [PROJECT_STATUS.md](PROJECT_STATUS.md) for current status, RAG improvement roadmap, and long-term Persona Museum vision.
