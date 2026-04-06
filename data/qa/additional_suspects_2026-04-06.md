# Additional Suspects — 2026-04-06

Post-cleanup shortlist from the rewritten corpus.

Status on 2026-04-06:

- Applied across `data/output`.
- Folded into `KNOWN_TEXT_REPLACEMENTS` in `src/persona_builder/process_transcripts.py`.
- Kept here as a dated approval record, not as procedure.

## Strong candidates

- `Fluminenje` / `fluminenje` -> `Fluminense`
  Context: Club World Cup discussion in `4Q78wT5SU5A`.

- `Alhilal` -> `Al-Hilal`
  Context: same chunk as above, Club World Cup.

- `Paciuka` -> `Pachuca`
  Context: same chunk as above, Mexican club.

- `Getwick` -> `Gatwick`
  Context: airport reference in `9EZ5IOrYgkE#3`.

- `Princetown` -> `Princeton`
  Context: `Harvard sau la Princetown` in `JwN3Myn9FbY#13`.

- `Sirina Williams` -> `Serena Williams`
  Context: `1xNuBsuykC8#10`.

- `Iisonul` -> `isonul`
  Context: Romanian expression `a ține isonul` in `lrpOBLBawT0#4`.

- `Julvern Vern` / `Julvernă` -> `Jules Verne`
  Context: multiple literary references in `0M_JDutvRnE`, `Hpym7VETn1I`, `JwN3Myn9FbY`.

- `Pavar` -> `Pavard`
  Context: Benjamin Pavard in football commentary.

- `Malic fofana` -> `Malick Fofana`
  Context: Lyon player reference in `fLoprytRru4#9-10`.

- `Tihad` -> `Etihad`
  Context: airline references in `2nogONpjbYY`, `Hpym7VETn1I`, `cGbAEoSULjg`.

- `Aatolah` / `aalahul` -> `Ayatollah` / `ayatollahul`
  Context: Iran discussion in `zFTn5zV9clo` and `6-IjSlJPzVo`.

- `Epstina` -> `Epstein`
  Context: `dosarele Epstina` in `McN80-DMvcc#19`.

## Medium confidence

- `Gărăbăc` -> probably `Qarabag` / `Qarabağ`
  Context: `Newcastle cu Gărăbăc` in `I8fbvayIees#3`.

- `Sweden Town` -> probably `Swindon Town`
  Context: lower-tier English club comparison in `I8fbvayIees#3`.

- `tipepsti` -> probably phrase-level `de tip Epstein`
  Context: `paranghelii de alea de tipepsti` in `3lcT8nDsvZo#1`.

## Leave manual

- `Cean Ceanuici Donnarumma`
  This may be ASR damage, but the surrounding chunk is Banciu imitating exaggerated commentary. High risk of overwriting deliberate mock delivery.

- `Bootweiserul` / `Goodweiser`
  Could be `Budweiser`, but this also looks like intentional mocking distortion.

- `Binoiule`
  Too unclear from text alone.

- `Catarul`
  In some places this may simply be colloquial pronunciation rather than an OCR/ASR mistake.
