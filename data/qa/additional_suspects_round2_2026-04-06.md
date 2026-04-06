# Additional Suspects Round 2 — 2026-04-06

Generated after applying the previous approval batch.

Status on 2026-04-06:

- Applied across `data/output`.
- `Lens` was normalized only in football phrase contexts so real `Lance Armstrong` references remain untouched.
- `Pitoiule` was left as manual-only because it still reads like deliberate mock delivery rather than a safe typo.

## High confidence exact replacements

- `Pălmeirăș` / `Palmeirăș` / `Palmeirș` -> `Palmeiras`
  Seen in `4Q78wT5SU5A#1`.

- `Benfic` -> `Benfica`
  Seen in `4Q78wT5SU5A#1`, `I8fbvayIees#4`, `MXfLvep0JUs#6`.

- `Texter` -> `Textor`
  Seen as `John Texter` in `4Q78wT5SU5A#1-2`, `9EZ5IOrYgkE#15`.

- `Paiet` -> `Payet`
  Seen in OM references in `4Q78wT5SU5A#5`, `9EZ5IOrYgkE#11`, `I8fbvayIees#13`.

- `Flotov` -> `Thauvin`
  Context is OM's goal-scorer in the 1-0 win at Paris; this is Florian Thauvin.
  Seen in `4Q78wT5SU5A#5`, `8VrhWsFOn88#9-10`.

- `Brandford` -> `Brentford`
  Seen in `TNV_RRE0thI#8-9`, `eEElPQQgj1Q#11`.

- `Qataru` -> `Qatarul`
  Seen in `4Q78wT5SU5A#5` and other PSG/Qatar ownership contexts.

- `Dezerbii` -> `De Zerbi`
  Seen in `4Q78wT5SU5A#2-3`, `6MsnTeL9nC4#8`.

- `Captown` -> `Cape Town`
  Seen in `6MsnTeL9nC4#14`, `CxifrFeKiDU#9`, `EOFxzEE_R8Q#2`.

- `Montpulieș` -> `Montpellier`
  Seen in `9EZ5IOrYgkE#12`.

- `Guirie` -> `Gouiri`
  Seen in `bfI29Z_MwjM#16`.

- `Cufeit` / `Cufeită` -> `Kuweit` / `Kuweit City`
  Seen in `8VrhWsFOn88#8`.

- `Marsei` -> `Marseille`
  Frequent football/city reference across the corpus.
  This one is exact-string safe, but it is common enough that it should be applied only if you want the corpus normalized away from Banciu's phonetic rendering.

## Medium confidence / phrase-level

- `Bot Fogul` / `bot fogu` -> `Botafogo`
  Same chunk as `Palmeiras`; likely intended as phonetic Brazilian pronunciation, so this is a judgment call.

- `Virț` -> `Wirtz`
  Seen in `6MsnTeL9nC4#4`, `6MsnTeL9nC4#13`, `bfI29Z_MwjM#16`.

- `Frpong` -> `Frimpong`
  Seen in `bfI29Z_MwjM#16`.

- `Hibier` -> `Højbjerg`
  Seen in OM contexts in `I8fbvayIees#2`, `f7Rw5P3ztsk#14`.

- `Hibierogbia`
  Probably a mangled lineup phrase around `Højbjerg` and nearby midfield names. Needs manual ear or phrase rewrite, not a blind token swap.

- `Graven Bersobo`
  Likely a collapsed Liverpool midfield phrase (`Gravenberch`, `Szoboszlai`). Needs phrase-level cleanup.

- `Lance`
  In football fixture contexts this may mean `Lens`, but global replacement would be unsafe because the corpus also contains `Lance Armstrong`.

- `Echit`
  In football lineups this may be `Ekitike`, but the token is too ambiguous for a blind global replace.

## Keep manual

- `Pitoiule`
  Could be a mocking delivery rather than ASR damage.

- `Cean Ceanuici ...`
  Already force-corrected once where approved; any remaining phrasing around that OM/PSG imitation commentary should be handled chunk-by-chunk, not token-by-token.
