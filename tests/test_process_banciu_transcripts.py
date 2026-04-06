from pathlib import Path

from persona_builder.process_transcripts import (
    analyze_corpus,
    apply_known_text_corrections,
    build_episode_json,
    clean_transcript_text,
    parse_subtitles,
    split_into_chunks,
)


def test_parse_subtitles_strips_intro_noise(tmp_path: Path) -> None:
    subtitle_path = tmp_path / "sample.ro.srt"
    subtitle_path.write_text(
        """1
00:00:00,000 --> 00:00:02,000
[Muzică]

2
00:00:02,000 --> 00:00:03,000
>> Ah.

3
00:00:03,000 --> 00:00:04,000
>> le monde avec un ami pour toi

4
00:00:04,000 --> 00:00:06,000
>> Noi suntem, fraților.

5
00:00:06,000 --> 00:00:08,000
Am reușit să depășim și aceste prime zile.

6
00:00:08,000 --> 00:00:10,000
[muzică]
""",
        encoding="utf-8",
    )

    parsed = parse_subtitles(subtitle_path)

    assert "Muzică" not in parsed
    assert "Ah" not in parsed
    assert "le monde" not in parsed
    assert parsed.startswith("Noi suntem, fraților.")


def test_split_into_chunks_uses_line_boundaries_when_punctuation_is_sparse() -> None:
    raw_text = "\n".join(
        [
            "Noi suntem aici și vorbim despre țara asta fără iluzii",
            "Pentru că oamenii ăștia au compromis tot ce se putea compromite",
            "În presă nu mai găsești aproape deloc coloană vertebrală",
            "Iar în fotbal vezi aceeași lipsă de caracter la fiecare pas",
            "Europa rămâne un reper chiar și atunci când se degradează",
            "România copiază decorul fără să înțeleagă fondul",
        ]
    )
    clean_text = clean_transcript_text(raw_text)

    chunks = split_into_chunks(clean_text, target_word_count=18, overlap_words=6)

    assert len(chunks) >= 2
    assert chunks[0].startswith("Noi suntem aici")
    assert chunks[1].startswith("Noi suntem aici") or chunks[1].startswith("Pentru că")
    assert "compromis tot" in chunks[1]
    assert "fără iluzii Pentru" in chunks[1]


def test_analyze_corpus_reports_noise_and_suspect_starts(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "episode.json").write_text(
        """{
  "episode_id": "ep1",
  "youtube_url": "https://example.com",
  "title": "Titlu",
  "date": "2024-01-01",
  "raw_text_length": 10,
  "num_chunks": 2,
  "chunks": [
    {"chunk_index": 0, "text": ">> ah acesta este un test", "approx_word_count": 5},
    {"chunk_index": 1, "text": "corect începe prost", "approx_word_count": 3}
  ]
}""",
        encoding="utf-8",
    )

    report = analyze_corpus(output_dir)

    assert report["episode_count"] == 1
    assert report["noise_tokens"]["ah"] == 1
    assert report["noise_tokens"][">>"] == 1
    assert report["suspect_starts"]


def test_apply_known_text_corrections_flattens_whitespace_and_restores_hyphens() -> None:
    text = "Într adevăr,\nnu\ns a\nspus că n a fost bine și\nmi a zis\nuitați vă la asta, dacă n o vezi."

    corrected = apply_known_text_corrections(text)

    assert "\n" not in corrected
    assert corrected == "Într-adevăr, nu s-a spus că n-a fost bine și mi-a zis uitați-vă la asta, dacă n-o vezi."


def test_build_episode_json_applies_storage_corrections() -> None:
    episode = build_episode_json(
        {
            "url": "https://www.youtube.com/watch?v=abc123",
            "title": "Titlu",
            "date": "2024-01-01",
        },
        cleaned_text="raw",
        chunks=["Brigit Bardau\nn a venit", "Airpons One și\nabține te"],
    )

    assert episode["num_chunks"] == 2
    assert episode["chunks"][0]["text"] == "Brigitte Bardot n-a venit"
    assert episode["chunks"][1]["text"] == "Air Force One și abține-te"
    assert episode["chunks"][1]["approx_word_count"] == 5


def test_apply_known_text_corrections_fixes_approved_name_suspects() -> None:
    text = (
        "Cioabiastoloș era pe la Euronws. "
        "Abib Bay juca cu Bornley, Leads, Bartm și Sanderland. "
        "Andre Pier Jinc și Medi Benasia vorbesc despre Bayern Münch. "
        "Cap Toownul, accontasem și bédition rămân suspecte. "
        "Fluminenje trece de Alhilal și Paciuka. "
        "Sirina Williams citește Julvern Vern la Princetown. "
        "Pălmeirăș joacă cu Bot Fogul, iar Benfic îl are pe John Texter. "
        "Paiet îl caută pe Flotov la Marsei. "
        "Brandford merge la Captown și în Qataru. "
        "Montpulieș, Guirie, Cufeit și Virț apar lângă Frpong, Hibier și Echit. "
        "OM Lance, PSG cu Lance, victoria de la Lance și jucătorul al lui Lance nu-l ating pe Lance Armstrong."
    )

    corrected = apply_known_text_corrections(text)

    assert "Csaba Asztalos" in corrected
    assert "Euronews" in corrected
    assert "Habib Beye" in corrected
    assert "Burnley" in corrected
    assert "Leeds" in corrected
    assert "Bournemouth" in corrected
    assert "Sunderland" in corrected
    assert "André-Pierre Gignac" in corrected
    assert "Medhi Benatia" in corrected
    assert "Bayern München" in corrected
    assert "Cape Townul" in corrected
    assert "contractasem" in corrected
    assert "prédictions" in corrected
    assert "Fluminense" in corrected
    assert "Al-Hilal" in corrected
    assert "Pachuca" in corrected
    assert "Serena Williams" in corrected
    assert "Jules Verne" in corrected
    assert "Princeton" in corrected
    assert "Palmeiras" in corrected
    assert "Botafogo" in corrected
    assert "Benfica" in corrected
    assert "John Textor" in corrected
    assert "Payet" in corrected
    assert "Thauvin" in corrected
    assert "Marseille" in corrected
    assert "Brentford" in corrected
    assert "Cape Town" in corrected
    assert "Qatarul" in corrected
    assert "Montpellier" in corrected
    assert "Gouiri" in corrected
    assert "Kuweit" in corrected
    assert "Wirtz" in corrected
    assert "Frimpong" in corrected
    assert "Højbjerg" in corrected
    assert "Ekitike" in corrected
    assert "OM Lens" in corrected
    assert "PSG cu Lens" in corrected
    assert "victoria de la Lens" in corrected
    assert "al lui Lens" in corrected
    assert "Lance Armstrong" in corrected
