# Persona Builder

Private MVP for a Radu Banciu chatbot.

The repo now has a conventional split:

- `src/persona_builder/`: actual code
- `data/`: inputs, corpus outputs, temp downloads, worldview artifact
- `tests/`: unit tests
- root: thin entrypoints and project config

The project status and immediate next steps live in [PROJECT_STATUS.md](/home/vladsft/persona-builder/PROJECT_STATUS.md).

## Current Stage

You are past the prototype stage.

What exists already:

- Streamlit chat app
- BM25 retrieval over local transcript chunks
- persona prompt grounded by a worldview document
- transcript ingestion pipeline with cleanup and QA

What remains:

- one episode from the current source list still needs audio transcription fallback
- manual answer-quality QA should happen before adding embeddings

## Repository Layout

```text
persona-builder/
├── app.py
├── fetch_banciu_videos.py
├── process_banciu_transcripts.py
├── extract_worldview.py
├── src/persona_builder/
├── data/
│   ├── input/
│   ├── output/
│   ├── samples/
│   ├── temp/
│   └── worldview/
├── tests/
├── Makefile
├── pyproject.toml
└── PROJECT_STATUS.md
```

## Recommended Setup

Install runtime dependencies:

```bash
make install
make editable
```

Run tests:

```bash
make test
```

Launch the app:

```bash
make app
```

## Secrets

Provide `ANTHROPIC_API_KEY` through environment variables or Streamlit secrets.

Optional runtime knobs:

- `MODEL`
- `TOP_K`
- `MAX_TOKENS`

Example `.streamlit/secrets.toml`:

```toml
ANTHROPIC_API_KEY = "..."
MODEL = "claude-haiku-4-5-20251001"
TOP_K = 5
MAX_TOKENS = 600
```

## Main Commands

Fetch or refresh the source CSV:

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

## Data Locations

- source list: `data/input/banciu_videos.csv`
- sample CSV: `data/samples/sample_videos.csv`
- processed corpus: `data/output/*.json`
- scratch downloads: `data/temp/`
- worldview file: `data/worldview/banciu_worldview.md`

## Preprocessing Dependencies

Runtime dependencies stay in `requirements.txt`.

Preprocessing-only dependencies are split into `requirements-preprocess.txt`:

```bash
make install-preprocess
```

That is only needed when fetching videos, downloading subtitles, or using Whisper fallback.

## What To Do Next

The short version:

1. `make install`
2. `make editable`
3. `make test`
4. `make qa`
5. `make app`

Then read [PROJECT_STATUS.md](/home/vladsft/persona-builder/PROJECT_STATUS.md) and decide whether to recover the one missing episode now or move to manual answer-quality QA first.
