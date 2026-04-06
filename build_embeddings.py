"""Generate and cache OpenAI embeddings for the transcript corpus."""

from pathlib import Path
import sys

SRC_DIR = Path(__file__).resolve().parent / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from persona_builder.paths import DEFAULT_OUTPUT_DIR
from persona_builder.retrieval import build_embeddings, load_corpus


def main() -> None:
    corpus = load_corpus(DEFAULT_OUTPUT_DIR)
    if not corpus:
        print(f"No corpus found in {DEFAULT_OUTPUT_DIR}. Run 'make process' first.")
        sys.exit(1)
    print(f"Corpus: {len(corpus)} chunks")
    embeddings = build_embeddings(corpus, DEFAULT_OUTPUT_DIR, force="--force" in sys.argv)
    print(f"Embeddings shape: {embeddings.shape}")


if __name__ == "__main__":
    main()
