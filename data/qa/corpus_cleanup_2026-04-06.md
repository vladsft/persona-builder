# Corpus Cleanup QA — 2026-04-06

This note is run-specific. Repeatable procedure now lives in `docs/corpus_cleanup_runbook.md`.

- Episodes scanned: 54
- Chunks scanned: 1054
- Existing corpus files rewritten in place: 54
- Embedded line breaks in stored chunk text: 0 remaining

## Run outcome

- Storage whitespace was normalized and `approx_word_count` recomputed.
- Conservative cratimă fixes were applied.
- The initial rare-token shortlist from this pass was later folded into the approved replacement map in `src/persona_builder/process_transcripts.py`.
- The remaining high-risk material was left for manual judgment rather than broad regex replacement.

## Residual manual-review areas

- French-heavy chunks
- imitation / mock-delivery passages
- phrase-level collapses where token boundaries are already broken
