# Radu Banciu Persona Builder

Build an AI persona based on Radu Banciu's YouTube shows using RAG (Retrieval-Augmented Generation).

## Overview

This project processes YouTube videos from Radu Banciu's show into cleaned, chunked transcripts ready for embedding and RAG pipelines.

## Scripts

### 1. `fetch_banciu_videos.py`

Searches YouTube for Radu Banciu videos by date and creates a CSV file with video metadata.

**Usage:**

```bash
# Use the predefined list of dates
python fetch_banciu_videos.py --use-default-dates --output-file banciu_videos.csv

# Or specify custom dates
python fetch_banciu_videos.py --dates "5 Decembrie" "27 Noiembrie" --output-file my_videos.csv --year 2024
```

**Predefined dates:**
- 5 Decembrie, 27 Noiembrie, 25 Noiembrie, 17 Noiembrie, 11 Noiembrie
- 3 Noiembrie, 31 Octombrie, 29 Octombrie, 22 Octombrie, 16 Octombrie
- 14 Octombrie, 11 Octombrie, 9 Octombrie, 17 Septembrie

The script searches for videos with titles matching:
- "Prea Mult Banciu - \<date\> | \<title\>"
- "PreaMultBanciu - \<date\> | \<title\>"

### 2. `process_banciu_transcripts.py`

Processes videos from the CSV file into cleaned transcript chunks.

**Usage:**

```bash
# Basic usage
python process_banciu_transcripts.py \
  --input-file banciu_videos.csv \
  --output-dir output

# Advanced options
python process_banciu_transcripts.py \
  --input-file banciu_videos.csv \
  --output-dir output \
  --temp-dir temp_downloads \
  --max-videos 5 \
  --whisper-model medium \
  --target-word-count 1200 \
  --overlap-words 100
```

**Options:**
- `--input-file`: CSV file with video metadata (from fetch_banciu_videos.py)
- `--output-dir`: Directory to save JSON files
- `--temp-dir`: Temporary directory for downloads (default: temp)
- `--max-videos`: Limit number of videos to process
- `--use-youtube-subtitles`: Try YouTube subtitles first (default: True)
- `--whisper-model`: Whisper model to use (tiny/base/small/medium/large, default: medium)
- `--target-word-count`: Target words per chunk (default: 1200)
- `--overlap-words`: Words to overlap between chunks (default: 100)

## Installation

```bash
# Install dependencies
pip install -r requirements.txt
```

**Note:** Whisper requires FFmpeg. Install it separately:
- **macOS:** `brew install ffmpeg`
- **Ubuntu/Debian:** `sudo apt update && sudo apt install ffmpeg`
- **Windows:** Download from https://ffmpeg.org/download.html

## Workflow

### Step 1: Fetch video metadata

```bash
python fetch_banciu_videos.py --use-default-dates --output-file banciu_videos.csv
```

This creates `banciu_videos.csv` with columns: `url`, `title`, `date`

### Step 2: Process videos into transcripts

```bash
python process_banciu_transcripts.py \
  --input-file banciu_videos.csv \
  --output-dir output
```

This creates JSON files in `output/` directory, one per video.

### Output Format

Each video produces a JSON file like `{video_id}.json`:

```json
{
  "episode_id": "video_id",
  "youtube_url": "https://youtube.com/watch?v=...",
  "title": "Prea Mult Banciu - 5 Decembrie | Episode Title",
  "date": "2024-12-05",
  "raw_text_length": 45678,
  "num_chunks": 8,
  "chunks": [
    {
      "chunk_index": 0,
      "text": "Full transcript chunk...",
      "approx_word_count": 1180
    }
  ]
}
```

## Project Structure

```
persona-builder/
├── fetch_banciu_videos.py       # Step 1: Search YouTube and create CSV
├── process_banciu_transcripts.py # Step 2: Process videos into chunks
├── requirements.txt              # Python dependencies
├── sample_videos.csv             # Example CSV format
├── README.md                     # This file
├── temp/                         # Temporary downloads (created by script)
└── output/                       # Output JSON files (created by script)
```

## Notes

- **Language:** All processing is configured for Romanian (subtitles and Whisper transcription)
- **Subtitles vs Whisper:** The script tries YouTube subtitles first (faster), then Whisper (slower but works without subtitles)
- **Whisper models:** `small` is fastest, `medium` balances speed/accuracy, `large` is most accurate but slowest
- **Error handling:** If a video fails, the script logs the error and continues with the next one
- **Temporary files:** Downloaded audio/subtitle files are kept in `temp_dir` for debugging

## Next Steps

After generating the JSON chunks, you can:
1. Create embeddings for each chunk using a model like `text-embedding-3-small`
2. Store embeddings in a vector database (Pinecone, Weaviate, ChromaDB, etc.)
3. Build a RAG pipeline to query Banciu's knowledge and speaking style
4. Fine-tune an LLM on the transcripts for persona-specific responses
