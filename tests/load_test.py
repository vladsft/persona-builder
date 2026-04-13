"""
Load test: simulate 50 concurrent sessions against the retrieval + rate-limit
pipeline.  This tests the components we control (BM25 retrieval, rate-limit
store, analytics logging) without making real LLM API calls.

Usage:
    python tests/load_test.py

The script imports the app internals directly rather than making HTTP requests
to Streamlit, since Streamlit Cloud runs a single-threaded Tornado server and
does not support standard HTTP load testing.  This validates that the
in-memory data structures hold under concurrent access.
"""

from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from pathlib import Path

# Ensure src is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from persona_builder.retrieval import (
    build_bm25_index,
    format_context_block,
    load_corpus,
    retrieve,
)
from persona_builder.streamlit_app import (
    RateLimitStore,
    _check_content,
    _detect_topics,
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

NUM_SESSIONS = 50
MESSAGES_PER_SESSION = 8
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "output"

SAMPLE_QUERIES = [
    "Ce parere ai despre Hagi?",
    "Cum vezi fotbalul romanesc?",
    "Ce crezi despre politicienii romani?",
    "Lucescu e cel mai bun antrenor?",
    "De ce e Romania asa cum e?",
    "Ce parere ai despre Becali?",
    "Cum e Ligue 1 anul asta?",
    "Ce crezi despre jurnalismul din Romania?",
]


def run_load_test() -> None:
    print(f"Loading corpus from {OUTPUT_DIR}...")
    if not OUTPUT_DIR.exists() or not list(OUTPUT_DIR.glob("*.json")):
        print("ERROR: No corpus files found. Run 'make process' first.")
        sys.exit(1)

    corpus = load_corpus(str(OUTPUT_DIR))
    bm25 = build_bm25_index(corpus)
    print(f"Corpus loaded: {len(corpus)} chunks")

    # Test 1: Concurrent retrieval
    print(f"\n--- Test 1: {NUM_SESSIONS} concurrent retrieval sessions ---")
    errors: list[str] = []
    results: list[float] = []
    lock = threading.Lock()

    def retrieval_worker(session_id: int) -> None:
        try:
            query = SAMPLE_QUERIES[session_id % len(SAMPLE_QUERIES)]
            t0 = time.perf_counter()
            hits = retrieve(query, bm25, corpus, top_k=5)
            elapsed = time.perf_counter() - t0

            # Validate results
            assert len(hits) > 0, f"Session {session_id}: no hits"
            assert all("text" in h for h in hits), f"Session {session_id}: malformed hits"

            # Run topic detection and content filter
            _detect_topics(query)
            for hit in hits:
                _check_content(hit["text"])

            # Format context
            format_context_block(hits)

            with lock:
                results.append(elapsed)
        except Exception as e:
            with lock:
                errors.append(f"Session {session_id}: {e}")

    threads = [
        threading.Thread(target=retrieval_worker, args=(i,))
        for i in range(NUM_SESSIONS)
    ]
    t_start = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    t_total = time.perf_counter() - t_start

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  {e}")
    else:
        print(f"  All {NUM_SESSIONS} sessions completed successfully")
        avg = sum(results) / len(results)
        p95 = sorted(results)[int(len(results) * 0.95)]
        print(f"  Total wall time: {t_total:.2f}s")
        print(f"  Avg retrieval: {avg*1000:.0f}ms")
        print(f"  P95 retrieval: {p95*1000:.0f}ms")
        print(f"  Throughput: {NUM_SESSIONS/t_total:.1f} sessions/sec")

    # Test 2: Rate limit store under concurrent access
    print(f"\n--- Test 2: Rate limit store concurrency ---")
    store = RateLimitStore()
    store_errors: list[str] = []
    accepted = 0
    rejected = 0
    count_lock = threading.Lock()

    def rate_limit_worker(session_id: int) -> None:
        nonlocal accepted, rejected
        try:
            ip_hash = hashlib.sha256(f"test_ip_{session_id % 10}".encode()).hexdigest()[:16]
            allowed, reason = store.check_and_register(ip_hash, max_per_ip=3, daily_cap=300)
            with count_lock:
                if allowed:
                    accepted += 1
                else:
                    rejected += 1
        except Exception as e:
            with count_lock:
                store_errors.append(f"Session {session_id}: {e}")

    threads = [
        threading.Thread(target=rate_limit_worker, args=(i,))
        for i in range(NUM_SESSIONS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    if store_errors:
        print(f"ERRORS ({len(store_errors)}):")
        for e in store_errors:
            print(f"  {e}")
    else:
        # 10 unique IPs, max 3 per IP = 30 accepted, 20 rejected
        print(f"  Accepted: {accepted}, Rejected: {rejected}")
        expected_max = 10 * 3  # 10 IPs × 3 sessions
        print(f"  Expected max accepted: {expected_max}")
        if accepted <= expected_max:
            print(f"  Rate limiting: CORRECT")
        else:
            print(f"  Rate limiting: FAILED (too many accepted)")

    # Test 3: Analytics logging under load
    print(f"\n--- Test 3: Concurrent analytics logging ---")
    log_dir = Path(__file__).resolve().parents[1] / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    test_log = log_dir / "_load_test.jsonl"
    if test_log.exists():
        test_log.unlink()

    log_errors: list[str] = []

    def log_worker(session_id: int) -> None:
        try:
            for msg_num in range(MESSAGES_PER_SESSION):
                entry = {
                    "session_id": f"load_test_{session_id}",
                    "message_number": msg_num + 1,
                    "timestamp": time.time(),
                }
                with open(test_log, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry) + "\n")
        except Exception as e:
            with lock:
                log_errors.append(f"Session {session_id}: {e}")

    threads = [
        threading.Thread(target=log_worker, args=(i,))
        for i in range(NUM_SESSIONS)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    expected_lines = NUM_SESSIONS * MESSAGES_PER_SESSION
    actual_lines = sum(1 for _ in test_log.open())
    test_log.unlink()  # cleanup

    if log_errors:
        print(f"ERRORS ({len(log_errors)}):")
        for e in log_errors:
            print(f"  {e}")
    else:
        print(f"  Expected log lines: {expected_lines}")
        print(f"  Actual log lines: {actual_lines}")
        if actual_lines == expected_lines:
            print(f"  Logging: CORRECT")
        else:
            print(f"  Logging: FAILED ({actual_lines} != {expected_lines})")

    # Summary
    print(f"\n{'='*50}")
    all_ok = not errors and not store_errors and not log_errors
    if all_ok and accepted <= expected_max and actual_lines == expected_lines:
        print("LOAD TEST PASSED")
    else:
        print("LOAD TEST FAILED — see errors above")
        sys.exit(1)


if __name__ == "__main__":
    run_load_test()
