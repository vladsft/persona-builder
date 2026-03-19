"""
BM25-based retrieval over Banciu episode transcript chunks.
No embeddings, no external APIs — works entirely in-memory.
"""

from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi

from .paths import DEFAULT_OUTPUT_DIR

WORD_RE = re.compile(r"\b[\wĂÂÎȘȚăâîșț'-]+\b", re.UNICODE)


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def tokenize_for_search(text: str) -> list[str]:
    """Normalize text for lexical retrieval while keeping display text intact."""
    normalized = _strip_accents(text.lower())
    return [token for token in WORD_RE.findall(normalized) if token]


def load_corpus(output_dir: str | Path = DEFAULT_OUTPUT_DIR) -> list[dict[str, Any]]:
    """Load all episode JSON files and return a flat list of chunk dicts."""
    base_dir = Path(output_dir)
    corpus: list[dict[str, Any]] = []
    for path in sorted(base_dir.glob("*.json")):
        with open(path, encoding="utf-8") as f:
            episode = json.load(f)
        for chunk in episode.get("chunks", []):
            corpus.append(
                {
                    "episode_id": episode["episode_id"],
                    "title": episode["title"],
                    "date": episode["date"],
                    "youtube_url": episode["youtube_url"],
                    "chunk_index": chunk["chunk_index"],
                    "text": chunk["text"],
                }
            )
    return corpus


def build_bm25_index(corpus: list[dict[str, Any]]) -> BM25Okapi:
    """Build a BM25 index over the corpus chunk texts."""
    tokenized = [tokenize_for_search(doc["text"]) for doc in corpus]
    return BM25Okapi(tokenized)


def retrieve(
    query: str,
    bm25: BM25Okapi,
    corpus: list[dict[str, Any]],
    top_k: int = 5,
    max_per_episode: int | None = None,
) -> list[dict[str, Any]]:
    """Return structured top_k retrieval hits with light diversification."""
    if not corpus:
        return []

    tokenized_query = tokenize_for_search(query)
    if not tokenized_query:
        return []

    scores = bm25.get_scores(tokenized_query)
    ranked_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)

    if max_per_episode is None:
        max_per_episode = max(1, math.ceil(top_k / 2))

    hits: list[dict[str, Any]] = []
    episode_counts: dict[str, int] = {}
    deferred_hits: list[dict[str, Any]] = []

    for index in ranked_indices:
        score = float(scores[index])
        doc = corpus[index]
        hit = {
            "episode_id": doc["episode_id"],
            "title": doc["title"],
            "date": doc["date"],
            "youtube_url": doc["youtube_url"],
            "chunk_index": doc["chunk_index"],
            "text": doc["text"],
            "score": score,
        }

        episode_id = hit["episode_id"]
        if episode_counts.get(episode_id, 0) < max_per_episode:
            hits.append(hit)
            episode_counts[episode_id] = episode_counts.get(episode_id, 0) + 1
            if len(hits) == top_k:
                return hits
        else:
            deferred_hits.append(hit)

    for hit in deferred_hits:
        hits.append(hit)
        if len(hits) == top_k:
            break

    return hits


def _truncate_chunk(text: str, max_words: int = 400) -> str:
    """Keep only the first *max_words* words of a chunk to save tokens."""
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words]) + " [...]"


def format_context_block(
    hits: list[dict[str, Any]], max_words_per_chunk: int = 400
) -> str:
    """Render structured retrieval hits into a prompt-friendly context block."""
    blocks = []
    for hit in hits:
        blocks.append(
            "\n".join(
                [
                    f"TITLU: {hit['title']}",
                    f"DATA: {hit['date']}",
                    f"SURSA: {hit['youtube_url']}",
                    f"FRAGMENT #{hit['chunk_index']} (score {hit['score']:.2f}):",
                    _truncate_chunk(hit["text"], max_words_per_chunk),
                ]
            )
        )
    return "\n\n---\n\n".join(blocks)

