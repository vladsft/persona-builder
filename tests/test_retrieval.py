import json
from pathlib import Path

from persona_builder.retrieval import build_bm25_index, format_context_block, load_corpus, retrieve, tokenize_for_search


def test_tokenize_for_search_normalizes_romanian_text() -> None:
    tokens = tokenize_for_search("Știri, Țară, jurnalism! În România?")

    assert tokens == ["stiri", "tara", "jurnalism", "in", "romania"]


def test_retrieve_returns_structured_hits_with_diversification() -> None:
    corpus = [
        {
            "episode_id": "ep1",
            "title": "Episod 1",
            "date": "2024-01-01",
            "youtube_url": "https://example.com/1",
            "chunk_index": 0,
            "text": "presa presa jurnalism jurnalism",
        },
        {
            "episode_id": "ep1",
            "title": "Episod 1",
            "date": "2024-01-01",
            "youtube_url": "https://example.com/1",
            "chunk_index": 1,
            "text": "presa și televiziune fără caracter",
        },
        {
            "episode_id": "ep2",
            "title": "Episod 2",
            "date": "2024-01-02",
            "youtube_url": "https://example.com/2",
            "chunk_index": 0,
            "text": "jurnalism onest și presă independentă",
        },
    ]
    bm25 = build_bm25_index(corpus)

    hits = retrieve("presa jurnalism", bm25, corpus, top_k=2)

    assert len(hits) == 2
    assert hits[0]["score"] >= hits[1]["score"]
    assert {hit["episode_id"] for hit in hits} == {"ep1", "ep2"}
    assert set(hits[0]) == {"episode_id", "title", "date", "youtube_url", "chunk_index", "text", "score"}


def test_load_corpus_and_format_context_block(tmp_path: Path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    (output_dir / "episode.json").write_text(
        json.dumps(
            {
                "episode_id": "ep1",
                "youtube_url": "https://example.com/watch?v=1",
                "title": "Titlu episod",
                "date": "2024-01-01",
                "raw_text_length": 42,
                "num_chunks": 1,
                "chunks": [{"chunk_index": 0, "text": "Europa și presa sunt teme recurente.", "approx_word_count": 6}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    corpus = load_corpus(str(output_dir))
    bm25 = build_bm25_index(corpus)
    hits = retrieve("Europa presă", bm25, corpus, top_k=1)
    context = format_context_block(hits)

    assert len(corpus) == 1
    assert hits[0]["title"] == "Titlu episod"
    assert "TITLU: Titlu episod" in context
    assert "SURSA: https://example.com/watch?v=1" in context
    assert "Europa și presa" in context
