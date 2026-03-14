from pathlib import Path

from persona_builder.process_transcripts import analyze_corpus, clean_transcript_text, parse_subtitles, split_into_chunks


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
