# Project Context: Radu Banciu AI Persona Builder

**Goal:** Build an AI persona based on Romanian TV host Radu Banciu using his YouTube videos for a RAG (Retrieval-Augmented Generation) pipeline.

**Current Progress:**

## ✅ Completed Steps:

1. **Created `fetch_banciu_videos.py`**
   - Searches YouTube for Radu Banciu videos by Romanian date (e.g., "5 Decembrie")
   - Tries both "Prea Mult Banciu" and "PreaMultBanciu" title formats
   - Generated `banciu_videos.csv` with **13 videos** from the requested dates

2. **Created `process_banciu_transcripts.py`**
   - Downloads Romanian subtitles from YouTube (subtitles available for all 13 videos - no Whisper needed!)
   - Cleans transcript text (removes [Music], normalizes whitespace)
   - Chunks text (~1200 words/chunk with 100-word overlap)
   - Saves JSON files to `output/` directory

3. **Successfully processed all 13 videos**
   - All videos had Romanian subtitles available
   - Generated 13 JSON files in `output/` folder
   - Each video has 8-11 chunks (~45K-60K characters per video)

## ⚠️ Current Issue:

**Chunking creates mid-sentence breaks** - The overlap mechanism cuts sentences in half at chunk boundaries (e.g., chunk 2 starts with "de exemplu, pe 7 decembrie..." which is mid-sentence from chunk 1).

**Why it matters:** While this works for RAG semantic search, cleaner sentence-boundary chunks would be better for:
- Readability
- Fine-tuning potential
- Better context preservation

## 🔧 What Needs to Be Done on New Machine:

1. **Fix chunking in `process_banciu_transcripts.py`:**
   - Modify `split_into_chunks()` function (lines ~241-290)
   - Make overlap sentence-aware (don't break mid-sentence)
   - Ensure chunks start at sentence boundaries

2. **Re-run processing:**
   ```bash
   python3 process_banciu_transcripts.py --input-file banciu_videos.csv --output-dir output
   ```

3. **Next steps after fixing chunks:**
   - Create embeddings for each chunk (use OpenAI `text-embedding-3-small` or similar)
   - Store in vector database (Pinecone, Weaviate, ChromaDB, etc.)
   - Build RAG query interface

## 📁 Project Structure:
```
persona-builder/
├── fetch_banciu_videos.py       # YouTube video finder
├── process_banciu_transcripts.py # Transcript processor (needs chunking fix)
├── banciu_videos.csv             # 13 videos metadata
├── requirements.txt              # yt-dlp, openai-whisper
├── output/                       # 13 JSON files with chunks
├── temp/                         # Downloaded subtitle files (.srt)
└── README.md                     # Documentation
```

## 🔑 Key Technical Details:

- **Language:** All processing is Romanian
- **Subtitle format:** SRT files (~100KB each)
- **Chunk size:** Target 1200 words, 100-word overlap
- **JSON structure per video:**
  ```json
  {
    "episode_id": "video_id",
    "youtube_url": "...",
    "title": "...",
    "date": "YYYY-MM-DD",
    "raw_text_length": 50000,
    "num_chunks": 9,
    "chunks": [
      {
        "chunk_index": 0,
        "text": "...",
        "approx_word_count": 1180
      }
    ]
  }
  ```

## 💡 Chunking Fix Needed:

The `split_into_chunks()` function needs to:
1. Split by sentences (current regex: `r'(?<=[.!?])\s+(?=[A-ZĂÂÎȘȚ])'`)
2. Accumulate sentences until ~1200 words
3. **When creating overlap:** Go back N sentences (not N words) to find overlap starting point
4. Ensure new chunk starts at a complete sentence

## 📋 Example of Current Problem:

**Chunk 1 ends with:**
> "...Ce fac dacă prostul lor ajunge la capitală? Adică ne ducem de două ori ca proștii să votăm. Păi n avem destul cu prostul pe care l avem."

**Chunk 2 starts with (MID-SENTENCE):**
> "de exemplu, pe 7 decembrie ajunge prostul de băluță la primăria generală? Păi ce facem?..."

This happens because the overlap grabs the last 100 words from chunk 1, which starts mid-sentence.

## 🎯 Desired Behavior:

**Chunk 1 should end at sentence boundary:**
> "...Ce fac dacă prostul lor ajunge la capitală? Adică ne ducem de două ori ca proștii să votăm. Păi n avem destul cu prostul pe care l avem."

**Chunk 2 should start at sentence boundary with overlap:**
> "Ce fac dacă prostul lor ajunge la capitală? Adică ne ducem de două ori ca proștii să votăm. Păi n avem destul cu prostul pe care l avem. Ce zice Dantă Pălagă?..."

The overlap should include complete sentences from the previous chunk, not word fragments.

---

**Copy this entire file to your new session and ask the agent to fix the chunking function and re-process the videos.**