"""
Extract Radu Banciu's worldview from processed transcript data.
"""

import json
import os
import sys
from pathlib import Path

from . import llm_client
from .paths import DEFAULT_OUTPUT_DIR, DEFAULT_WORLDVIEW_PATH, ensure_repo_layout

DEFAULT_WORLDVIEW_MODELS = {
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4.1-mini",
    "gemini": "gemini-2.5-pro",
}

PASS1_PROMPT = """\
Ești un analist care studiază stilul și gândirea lui Radu Banciu, comentator TV român.

Ai primit transcriptul unui episod din emisiunea lui. Analizează-l și extrage:

1. **Pozițiile exprimate** — ce opinii concrete susține în acest episod? (despre politicieni, instituții, evenimente, persoane publice)
2. **Teme recurente** — ce subiecte revine frecvent? (România, Europa, fotbal, presă, clasa politică, etc.)
3. **Judecăți de valoare** — ce admiră? ce disprețuiește? ce consideră inacceptabil?
4. **Ținte ale criticii** — cine sunt oamenii sau tipologiile pe care le atacă? cu ce argumente?
5. **Cadrul interpretativ** — cum explică el lucrurile? care e logica din spatele opiniilor lui?
6. **Expresii și formulări distinctive** — citate directe sau formulări tipice care surprind vocea lui

Scrie analiza în română. Fii specific — citează din text când e relevant. Nu rezuma vag, extrage substanța.
"""

PASS2_PROMPT = """\
Ești un analist care sintetizează viziunea despre lume a lui Radu Banciu, bazat pe analiza a {n_episodes} episoade din emisiunea lui.

Mai jos ai rezumatele per-episod. Sintetizează-le într-un document structurat care surprinde FILOZOFIA lui coerentă — \
nu opiniile punctuale, ci sistemul de valori din care derivă acele opinii.

Documentul trebuie să permită cuiva care nu l-a văzut niciodată pe Banciu să înțeleagă cum gândește \
și să poată prezice ce ar spune despre un subiect nou.

Scrie documentul cu următoarele secțiuni. Pentru fiecare secțiune, fii specific și concret — \
cu exemple din episoade, nu cu generalități. Documentul e în română.

## Diagnosticul României
Ce a mers prost după comunism. De ce instituțiile sunt bolnave. Teoria lui despre clasa politică, \
despre mentalitatea colectivă, despre ce a ratat România în tranziție.

## Viziunea despre Europa și Civilizație
Ce înseamnă Europa pentru el — nu UE birocratic, ci idealul civilizațional. \
Vestul real vs. Vestul idealizat de români. Cum vede România față de restul Europei.

## Fotbalul ca Metaforă Morală
Cum folosește fotbalul pentru a vorbi despre caracter, mediocritate, onestitate, trădare. \
Ce îl supără la fotbalul românesc dincolo de rezultate. Cum leagă fotbalul de societate.

## Inamicii Recurenți
Categorii de oameni față de care are dispreț consistent — tipologii, nu doar persoane. \
Impostorul, mediocrul pretențios, omul care "s-a vândut", politicianul care se victimizează, etc.

## Ce Nu Ar Spune Niciodată
Poziții fundamental incompatibile cu valorile lui. Lucruri pe care nu le-ar susține \
indiferent de context. Acestea sunt "liniile roșii" ale personajului.

## Teoria despre Jurnalism și Opinia Publică
Ce crede că face presa română și ce ar trebui să facă. De ce are dispreț pentru mulți colegi. \
Ce înseamnă pentru el "a spune adevărul" față de "a face audiență".

## Alte Constante
Orice altceva esențial: relația cu trecutul, cu nostalgia, cu vârsta, cu bătrânețea societății. \
Viziunea despre ce înseamnă caracter, rezistență, demnitate.

---

Rezumatele per-episod:

{summaries}
"""


def load_episodes() -> list[dict]:
    episodes = []
    for path in sorted(Path(DEFAULT_OUTPUT_DIR).glob("*.json")):
        with open(path, encoding="utf-8") as f:
            episodes.append(json.load(f))
    return episodes


def pass1_summarize(episode: dict) -> str:
    full_text = "\n\n".join(chunk["text"] for chunk in episode["chunks"])
    if len(full_text) > 80000:
        full_text = full_text[:80000] + "\n\n[...truncat...]"

    print(f"  Pass 1: {episode['title'][:60]}... ({len(full_text)} chars)")
    provider = llm_client.get_provider()
    default_model = DEFAULT_WORLDVIEW_MODELS.get(provider, DEFAULT_WORLDVIEW_MODELS["anthropic"])
    model = os.getenv("WORLDVIEW_MODEL", default_model)
    text = llm_client.create(
        model=model,
        system="",
        messages=[
            {
                "role": "user",
                "content": f"{PASS1_PROMPT}\n\n---\n\nTITLU EPISOD: {episode['title']}\nDATA: {episode['date']}\n\nTRANSCRIPT:\n{full_text}",
            }
        ],
        max_tokens=2000,
    )
    return f"### {episode['title']} ({episode['date']})\n\n{text}"


def pass2_synthesize(summaries: list[str]) -> str:
    combined = "\n\n---\n\n".join(summaries)
    prompt = PASS2_PROMPT.format(n_episodes=len(summaries), summaries=combined)
    print(f"\n  Pass 2: Synthesizing {len(summaries)} episode summaries...")
    provider = llm_client.get_provider()
    default_model = DEFAULT_WORLDVIEW_MODELS.get(provider, DEFAULT_WORLDVIEW_MODELS["anthropic"])
    model = os.getenv("WORLDVIEW_MODEL", default_model)
    return llm_client.create(
        model=model,
        system="",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4096,
    )


def main() -> None:
    ensure_repo_layout()

    try:
        llm_client.get_api_key()
    except RuntimeError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    episodes = load_episodes()
    if not episodes:
        print(f"No episode JSON files found in {DEFAULT_OUTPUT_DIR}/")
        sys.exit(1)

    print(f"Found {len(episodes)} episodes. Starting worldview extraction...\n")
    summaries = [pass1_summarize(episode) for episode in episodes]
    worldview = pass2_synthesize(summaries)

    header = (
        "# Viziunea lui Radu Banciu — Extras din Corpus\n\n"
        "<!-- Generat automat din analiza a "
        f"{len(episodes)} episoade. Revizuiește și editează înainte de utilizare. -->\n\n"
    )
    worldview_path = Path(DEFAULT_WORLDVIEW_PATH)
    worldview_path.parent.mkdir(parents=True, exist_ok=True)
    worldview_path.write_text(header + worldview, encoding="utf-8")
    print(f"\nWorldview document written to {worldview_path}")
    print("Please review and edit before using in the chatbot.")


if __name__ == "__main__":
    main()

