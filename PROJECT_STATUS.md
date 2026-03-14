# Project Status

## Current Stage

The project is now at **private MVP / developer-polish stage**.

What already exists:

- a working Streamlit chat app
- BM25 retrieval over local transcript chunks
- a worldview-grounded persona prompt
- a transcript ingestion pipeline with subtitle cleanup and corpus QA

What is not done yet:

- the corpus is not fully complete for the current source list
- one episode still needs audio transcription fallback
- answer quality still needs deliberate manual QA across topic areas

## Current Repo Shape

- `src/persona_builder/`: actual application and pipeline code
- `data/input/`: source CSVs
- `data/output/`: processed episode JSON corpus
- `data/temp/`: downloaded subtitle/audio scratch files
- `data/worldview/`: worldview document used by the app
- `tests/`: unit tests

Root files are now mostly entrypoints and project config.

## Where We Are Right Now

- source list: `27` videos in `data/input/banciu_videos.csv`
- regenerated corpus available: `26` episodes in `data/output/`
- current missing episode: `2024-10-09`
- reason: YouTube has no Romanian captions for that episode, so it needs audio transcription
- tests: passing
- app boot: verified locally

## What To Do Now

1. Install the normal runtime dependencies:

```bash
make install
make editable
```

2. Run the app and manually QA answers:

```bash
make app
```

Suggested QA prompts:

- Romanian politics
- Europe / civilizație
- presă / jurnalism
- fotbal / caracter

3. Decide whether you want to recover the missing `2024-10-09` episode now.

If yes:

- install preprocessing deps
- install or provide a Whisper-capable environment
- rerun transcript processing

4. If answer quality is good enough, stop here and keep BM25 for now.

5. If answer quality is not good enough, the next technical step should be **hybrid or embedding-based retrieval**, not more repo churn.

## Practical Next Command Set

For the most sensible immediate path:

```bash
make install
make editable
make test
make qa
make app
```

If you want to continue corpus work:

```bash
make install-preprocess
python process_banciu_transcripts.py
python process_banciu_transcripts.py --qa-only
```
