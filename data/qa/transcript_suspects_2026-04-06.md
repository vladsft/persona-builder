# Transcript Suspects — 2026-04-06

Fresh QA pass after corpus reprocess with 600-word chunks (54 episodes, ~956 chunks).

This is a dated findings note. Repeatable workflow now lives in `docs/corpus_cleanup_runbook.md`.

## Auto-fixable: replacement map (76 occurrences across 26 episodes)

These are confirmed misspellings from YouTube auto-subtitles. Each pattern appears consistently across episodes.

| Bad | Good | Count | Notes |
|-----|------|-------|-------|
| `Sarcozi` | `Sarkozy` | 7 | 7 episodes |
| `TJV` | `TGV` | 6 | mainly ep 19 Ianuarie (French trains discussion) |
| `Giordan Bardela` | `Jordan Bardella` | 4 | |
| `Brigit Bardau` | `Brigitte Bardot` | 4 | |
| `Leopen` / `Lăpen` | `Le Pen` | 4 | |
| `de Zerbii` | `De Zerbi` | 3 | |
| `Lavră` / `Liavră` / `Leavră` | `Le Havre` | 5 | |
| `Novisad` / `Novisadă` | `Novi Sad` | 3 | |
| `Jospan` | `Jospin` | 2 | |
| `Brigit Bardo` | `Brigitte Bardot` | 2 | variant of Bardau |
| `Brijit` / `brijit` | `Brigitte` | 2 | |
| `Ghansbur` / `Ghansburg` / `Gansburg` | `Gainsbourg` | 4 | |
| `Cron Montana` / `Crom Montana` | `Crans-Montana` | 3 | |
| `Cabi Alonso` | `Xabi Alonso` | 2 | |
| `Westam` / `Westham` | `West Ham` | 3 | |
| `rusorainean` / `rusoraineană` | `ruso-ucrainean(ă)` | 2 | |
| `Ursula Fonder` (Derlion) | `Ursula von der Leyen` | 2 | |
| `LCBTQ` | `LGBTQ` | 2 | |
| `Catrin Donun` | `Catherine Deneuve` | 1 | |
| `Isabela Giani` | `Isabelle Adjani` | 1 | |
| `Hugo Cave` | `Hugo Chavez` | 1 | |
| `Airpons One` | `Air Force One` | 1 | |
| `Del Rodriguez` | `Delcy Rodriguez` | 1 | |
| `Mamadu` | `Mamadou` | 1 | |
| `media partul` | `Mediapart` | 1 | |
| `ezbolac` | `Hezbollah` | 1 | |
| `cerciliană` | `churchilliană` | 1 | |
| `Ajaxo` | `Ajaccio` | 1 | |
| `Mengladba` / `Mhengland` | `Mönchengladbach` | 2 | |
| `Real Iedo` | `Real Oviedo` | 1 | |
| `o Sasunia` | `Osasuna` | 1 | |

### Episodes with most hits

| Episode | Date | Hits |
|---------|------|------|
| Furios pe norvegieni... Trump vrea Groenlanda! | 2026-01-19 | 14 |
| Războaiele la zi: a 4-a în Iran... | 2026-03-03 | 12 |
| Prima Doamnă a României... | 2026-03-23 | 5 |
| Balonul de Aur... PSG - Strasbourg | 2025-10-16 | 7 |
| Ce ascunde capturarea lui Maduro...? | 2026-01-06 | 4 |
| Trump: „Vrem și noi o bucată de gheață..." | 2026-01-21 | 5 |

---

## French passages (intentional — Banciu speaks French on air)

These chunks contain substantial French text. The auto-subtitles transcribe them poorly since they expect Romanian.

### Heavy French (score > 0.15 — majority French text)

- **iAM Banciu - 27 Iunie** (`4Q78wT5SU5A`)
  chunk #0: faux-French poetry/verse opening about Marseille football
  chunk #9: French passage about Burkina Faso / La Charl Rois
  → This episode has the most French of any in the corpus

- **iAM Banciu - 24 Februarie** (`I8fbvayIees`)
  chunk #10: French football commentary / Bodø/Glimt discussion

### Light French (score 0.08–0.15 — French phrases mixed into Romanian)

- **Prea Mult Banciu - 27 Martie** (`MXfLvep0JUs`) chunk #16: "monsieur bonou et votre nom oui Banu et il venda du fromage"
- **Prea Mult Banciu - 23 Martie** (`2nogONpjbYY`) chunk #1: Jospin resignation quote "Je quitte ce soir la politique française"
- **Prea Mult Banciu - 4 Martie** (`QkS2Ugop758`) chunk #16
- **PreaMultBanciu - 14 Octombrie** (`JwN3Myn9FbY`) chunk #14: Siri / French interjections

---

## Watch on YouTube: still needs a human ear

These are passages where the correct form can't be determined from text alone.

- **iAM Banciu - 27 Iunie** (`4Q78wT5SU5A`)
  Seek: `~02:12`
  The whole faux-French opening is unstable. Consider trimming chunk #0 or leaving as-is (it's atmosphere, not information).

- **iAM Banciu - 24 Februarie** (`I8fbvayIees`)
  Seek: `~43:21`
  French team/score words drifting. Suspects: `Abibe` / `Bimbe` / `Abib Bay` → probably `Habib Beye`; `Tèqus` → `Tchèques`

- **iAM Banciu - 16 Octombrie** (`TNV_RRE0thI`)
  Seek: `~22:31` to `~40:03`
  Densest football-name drift zone. Suspects beyond the auto-fixable list: `Bastian de Shepi` → unclear

- **Prea Mult Banciu - 29 Octombrie** (`tPQeAj7W_kY`)
  Seek: `~56:39`
  Opening French sentence is malformed from the first word.

- **PreaMultBanciu - 14 Octombrie** (`JwN3Myn9FbY`)
  Seek: `~57:34`
  Siri prompt + surrounding French line badly mangled.

- **Prea Mult Banciu - 11 Aprilie** (`3j0lf2IIL3E`)
  Seek: `~60:54`
  French listener question too garbled to repair from text alone.

---

## Patterns NOT found (clean in new corpus)

These were in the old QA file but are no longer present — either the rechunking dropped them or they were in episodes no longer in the corpus:

`Burnley`, `Cherki`, `Getafe`, `Nottingham`, `Sunderland`, `Wolves`, `football club de Metz`, `hockey`, `Lupul nu Pagadi`
