# Corpus Cleanup Runbook

This guide is the repeatable procedure for cleaning `data/output` from scratch.

Use it when:

- chunk sizes drift from the intended setting
- newline / whitespace pollution gets into stored chunk text
- subtitle ASR errors start hurting retrieval quality
- you need a fresh QA pass on duplicates, suspect tokens, or badly transcribed names

This file is for procedure. Dated findings belong in `data/qa/`.

## Source of truth

- Corpus JSON: `data/output/*.json`
- Video list: `data/input/banciu_videos.csv`
- Transcript processor: `src/persona_builder/process_transcripts.py`
- Regression tests: `tests/test_process_banciu_transcripts.py`

## Safety rules

1. Do not blindly global-replace tokens that can also be valid names in other contexts.
2. Prefer exact replacements or phrase-scoped replacements over broad regex.
3. Treat mock delivery, stuttering, and faux-French as high-risk zones.
4. Keep QA notes factual and dated. Do not store generic workflow there.
5. Recompute `approx_word_count` any time chunk text changes.

## Standard workflow

### 1. Audit the corpus first

Check file count, chunk sizes, and any obvious noise.

Useful commands:

```bash
./.venv/bin/python -m persona_builder.process_transcripts --qa-only --output-dir data/output
rg -n "\\\\n" data/output
```

What to look for:

- max chunk size drifting above the intended target
- `>>`, filler tokens, or bad chunk starts
- embedded line breaks still stored inside chunk text

### 2. Check duplicate episodes carefully

Use both:

- exact `youtube_url`
- extracted YouTube video ID

Do not rely on filename alone.

If two files point to the same Banciu episode:

1. confirm they are the same video by URL or video ID
2. prefer the better-normalized file
3. if one is an old 1200-word version and the other is a 600-word version of the same link, keep the 600-word one
4. if there is no clear better file, regenerate and keep one canonical JSON

### 3. Verify chunk-size consistency

Current expected defaults in `process_transcripts.py`:

- `target_word_count = 600`
- `overlap_words = 50`

If you find old 1200-word chunks, that usually means the corpus is mixed across generations.

Recommended action:

- reprocess the affected episodes with the current chunk settings
- overwrite the stale JSON in place

If an episode is no longer in `banciu_videos.csv`, reuse the metadata already stored in the existing JSON (`youtube_url`, `title`, `date`) and regenerate from there.

### 4. Normalize storage format before higher-level correction

Always flatten stored chunk text before any lexical cleanup.

Required invariants:

- no embedded `\\n` inside chunk `text`
- single-space internal whitespace
- updated `approx_word_count`

This is handled by:

- `normalize_text_for_storage()`
- `apply_known_text_corrections()`
- `build_episode_json()`

in `src/persona_builder/process_transcripts.py`.

### 5. Apply only conservative Romanian grammar fixes automatically

Safe automatic fixes are mostly lost-cratimă cases where the split form is almost certainly wrong:

- `n-a`, `n-au`, `n-are`, `n-am`, `n-ai`, `n-o`
- `s-a`, `s-au`, `s-ar`, `s-o`
- `mi-a`, `mi-am`
- `ți-a`, `ți-am`, `ți-ai`, `ți-au`, `ți-ar`
- `i-a`, `i-au`, `i-am`
- `l-a`, `l-au`, `l-am`, `l-ați`, `l-o`
- `m-a`, `m-am`, `m-ai`, `m-au`
- `te-ai`, `te-au`
- `v-a`, `v-am`
- `ne-a`, `ne-am`
- `le-a`, `le-am`
- `și-a`, `și-au`, `și-ar`
- `nu-i`, `nu-l`, `nu-mi`
- `într-un`, `dintr-un`, `printr-un`, `într-adevăr`
- `uitați-vă`, `duceți-vă`, `abține-te`

Do not expand this list casually. If a pattern could be valid in normal Romanian or in quoted speech, keep it out of the auto-fix set.

### 6. Maintain a curated replacement map for proper names and obvious ASR drift

Use `KNOWN_TEXT_REPLACEMENTS` for:

- people
- clubs
- cities
- airlines
- institutions
- obvious subtitle distortions

Examples of safe replacements that were approved in this corpus:

- `euronws` -> `Euronews`
- `Cioabiastoloș` -> `Csaba Asztalos`
- `Fluminenje` -> `Fluminense`
- `Alhilal` -> `Al-Hilal`
- `Paciuka` -> `Pachuca`
- `Texter` -> `Textor`
- `Paiet` -> `Payet`
- `Flotov` -> `Thauvin`

Keep replacements case-insensitive unless there is a specific reason not to.

### 7. Use the offenders heuristic for new suspect discovery

The basic idea:

1. tokenize the corpus
2. rank low-frequency alphabetic tokens
3. inspect weird tokens that appear too rarely to be standard vocabulary
4. cluster them by context before deciding on a correction

This is good for catching:

- malformed proper names
- foreign clubs and places
- obvious OCR / ASR drift

This is bad for:

- French passages
- imitation/stuttering
- deliberate mocking pronunciations
- uncommon but real surnames

Practical rule:

- a rare token is a lead, not a replacement order

### 8. Bucket suspects before applying them

Every suspect should go into one of three buckets:

#### High confidence

Apply directly.

Criteria:

- obvious intended referent
- repeated consistently across contexts
- no realistic competing interpretation

#### Needs approval

Present as a shortlist first.

Criteria:

- probably right, but not fully safe
- depends on football context, French context, or a specific public figure
- one wrong global replace could damage unrelated text

#### Manual-only

Do not auto-fix.

Criteria:

- mock stuttering
- deliberate distortion for comic effect
- faux-French or multilingual passages
- badly collapsed phrases where the token boundaries are already broken

### 9. Handle known trap cases carefully

#### `Lens` vs `Lance`

Do not globally replace `Lance` with `Lens`.

Reason:

- the corpus also contains legitimate `Lance Armstrong`

Use phrase-scoped corrections only in football contexts such as:

- `OM Lance` -> `OM Lens`
- `la Lance` -> `la Lens`
- `câștigând la Lance` -> `câștigând la Lens`
- `al lui Lance` -> `al lui Lens`

#### Mock delivery / stuttering

If a malformed token may reflect Banciu imitating someone, leave it alone unless the intended form is unquestionably recoverable.

#### French-heavy chunks

Do not over-normalize these with Romanian assumptions.
Treat them as:

- leave as-is
- manually review
- or mark as lower-value retrieval material if needed

### 10. Apply approved fixes in code first, then rewrite the corpus

Order matters:

1. update `KNOWN_TEXT_REPLACEMENTS` / safe regex rules in `process_transcripts.py`
2. update tests in `tests/test_process_banciu_transcripts.py`
3. run the normalizer over existing `data/output/*.json`
4. rerun QA scans

The stored corpus should always match what the processor would write today.

### 11. Keep QA notes narrow and dated

Good QA note contents:

- run date
- counts
- suspect list
- status of approved / unapplied / manual-only items
- unresolved chunks needing a human ear

Bad QA note contents:

- generic workflow
- repeatable policy
- long explanations of the normalizer design

That material belongs in this runbook.

### 12. Verify after every cleanup pass

Minimum verification:

```bash
./.venv/bin/pytest -q tests/test_process_banciu_transcripts.py tests/test_retrieval.py
./.venv/bin/python -m persona_builder.process_transcripts --qa-only --output-dir data/output
rg -n "\\\\n" data/output
```

Also run targeted `rg` searches for the suspect tokens you intended to remove.

Important:

- do not trust substring matches alone
- check word boundaries
- confirm that the remaining hits are either legitimate or intentionally left alone

## Output checklist

A cleanup pass is complete only when all of the following are true:

- no duplicate episodes remain by URL or video ID
- chunk sizes match the intended regime
- no stored chunk text contains embedded newlines
- approved replacements are present in code and in corpus JSON
- `approx_word_count` has been recomputed where needed
- QA notes reflect findings, not procedure
- tests pass

## When to stop

Stop the automatic pass when the remaining suspects are mostly:

- comedic distortions
- multilingual drift
- ambiguous football lineups
- phrase-level collapses that need a human ear

Past that point, more global replacement usually makes the corpus worse, not better.
