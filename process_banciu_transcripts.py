#!/usr/bin/env python3
"""
Process Radu Banciu YouTube videos into cleaned transcript chunks.

This script downloads YouTube videos, extracts or transcribes Romanian speech,
cleans the text, and chunks it for later use in a RAG pipeline.
"""

import argparse
import csv
import json
import logging
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional
from urllib.parse import parse_qs, urlparse

import yt_dlp
import whisper


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_video_list(input_file: str) -> List[Dict[str, str]]:
    """
    Load video information from a CSV file.

    Args:
        input_file: Path to CSV file with columns: url, title, date

    Returns:
        List of dicts with keys: url, title, date
    """
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    videos = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if 'url' not in row or 'title' not in row or 'date' not in row:
                logger.warning(f"Skipping row with missing fields: {row}")
                continue
            videos.append({
                'url': row['url'].strip(),
                'title': row['title'].strip(),
                'date': row['date'].strip()
            })

    logger.info(f"Loaded {len(videos)} videos from {input_file}")
    return videos


def extract_video_id(url: str) -> Optional[str]:
    """
    Extract YouTube video ID from URL.

    Args:
        url: YouTube video URL

    Returns:
        Video ID string or None if not found
    """
    parsed = urlparse(url)

    # Handle youtu.be short URLs
    if parsed.hostname == 'youtu.be':
        return parsed.path[1:]

    # Handle youtube.com URLs
    if parsed.hostname in ('www.youtube.com', 'youtube.com'):
        if parsed.path == '/watch':
            query = parse_qs(parsed.query)
            return query.get('v', [None])[0]
        elif parsed.path.startswith('/embed/'):
            return parsed.path.split('/')[2]
        elif parsed.path.startswith('/v/'):
            return parsed.path.split('/')[2]

    return None


def download_subtitles_or_audio(
    video_info: Dict[str, str],
    temp_dir: Path,
    use_youtube_subtitles: bool = True
) -> Dict[str, str]:
    """
    Download Romanian subtitles or audio from YouTube video.

    Args:
        video_info: Dict with 'url', 'title', 'date'
        temp_dir: Directory to store downloaded files
        use_youtube_subtitles: Whether to try YouTube subtitles first

    Returns:
        Dict with 'type' ('subtitles' or 'audio') and 'path' (file path)
    """
    video_id = extract_video_id(video_info['url'])
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {video_info['url']}")

    temp_dir.mkdir(parents=True, exist_ok=True)

    # Try to download Romanian subtitles first
    if use_youtube_subtitles:
        subtitle_path = temp_dir / f"{video_id}.ro.srt"

        ydl_opts_subs = {
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['ro'],
            'subtitlesformat': 'srt',
            'skip_download': True,
            'outtmpl': str(temp_dir / video_id),
            'quiet': True,
            'no_warnings': True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts_subs) as ydl:
                ydl.download([video_info['url']])

            # Check if subtitle file was created
            if subtitle_path.exists():
                logger.info(f"Downloaded Romanian subtitles for {video_id}")
                return {'type': 'subtitles', 'path': str(subtitle_path)}
        except Exception as e:
            logger.warning(f"Failed to download subtitles for {video_id}: {e}")

    # Fallback: download audio
    audio_path = temp_dir / f"{video_id}.m4a"

    ydl_opts_audio = {
        'format': 'bestaudio/best',
        'outtmpl': str(temp_dir / f"{video_id}.%(ext)s"),
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
        }],
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([video_info['url']])

        logger.info(f"Downloaded audio for {video_id}")
        return {'type': 'audio', 'path': str(audio_path)}
    except Exception as e:
        raise RuntimeError(f"Failed to download audio for {video_id}: {e}")


def parse_subtitles(subtitle_path: Path) -> str:
    """
    Parse SRT subtitle file and extract text.

    Args:
        subtitle_path: Path to .srt file

    Returns:
        Concatenated subtitle text
    """
    with open(subtitle_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # SRT format: number, timestamp, text, blank line
    # Remove sequence numbers and timestamps, keep only text
    lines = content.split('\n')
    text_lines = []

    for line in lines:
        line = line.strip()
        # Skip empty lines, numbers, and timestamp lines
        if not line or line.isdigit() or '-->' in line:
            continue
        text_lines.append(line)

    return ' '.join(text_lines)


def transcribe_audio_with_whisper(audio_path: Path, model_name: str = "medium") -> str:
    """
    Transcribe audio file to Romanian text using Whisper.

    Args:
        audio_path: Path to audio file
        model_name: Whisper model to use (tiny, base, small, medium, large)

    Returns:
        Transcribed text
    """
    logger.info(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)

    logger.info(f"Transcribing audio: {audio_path}")
    result = model.transcribe(
        str(audio_path),
        language='ro',
        verbose=False
    )

    return result['text']


def clean_transcript_text(raw_text: str) -> str:
    """
    Clean and normalize transcript text.

    Args:
        raw_text: Raw transcript text

    Returns:
        Cleaned text
    """
    text = raw_text

    # Remove common placeholder tokens
    placeholders = [
        r'\[Music\]', r'\[Applause\]', r'\[Laughter\]',
        r'\[music\]', r'\[applause\]', r'\[laughter\]',
        r'\[MUSIC\]', r'\[APPLAUSE\]', r'\[LAUGHTER\]'
    ]
    for placeholder in placeholders:
        text = re.sub(placeholder, '', text)

    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)

    # Replace multiple newlines with double newline (paragraph separator)
    text = re.sub(r'\n\n+', '\n\n', text)

    # Strip leading/trailing whitespace
    text = text.strip()

    return text


def split_into_chunks(
    clean_text: str,
    target_word_count: int = 1200,
    overlap_words: int = 100
) -> List[str]:
    """
    Split text into overlapping chunks respecting sentence boundaries.

    Args:
        clean_text: Cleaned transcript text
        target_word_count: Target words per chunk (soft upper bound)
        overlap_words: Number of words to overlap between chunks

    Returns:
        List of text chunks
    """
    # Split into sentences (simple heuristic)
    # Match period, question mark, or exclamation followed by space and uppercase
    sentence_pattern = r'(?<=[.!?])\s+(?=[A-ZĂÂÎȘȚ])'
    sentences = re.split(sentence_pattern, clean_text)

    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        sentence_words = sentence.split()
        sentence_word_count = len(sentence_words)

        # If adding this sentence exceeds target, save current chunk and start new one
        if current_word_count + sentence_word_count > target_word_count and current_chunk:
            # Save current chunk
            chunks.append(' '.join(current_chunk))

            # Start new chunk with overlap from previous chunk
            if overlap_words > 0:
                all_words = ' '.join(current_chunk).split()
                overlap_start = max(0, len(all_words) - overlap_words)
                current_chunk = [' '.join(all_words[overlap_start:])]
                current_word_count = len(current_chunk[0].split())
            else:
                current_chunk = []
                current_word_count = 0

        current_chunk.append(sentence)
        current_word_count += sentence_word_count

    # Add remaining chunk
    if current_chunk:
        chunks.append(' '.join(current_chunk))

    return chunks


def build_episode_json(
    video_info: Dict[str, str],
    cleaned_text: str,
    chunks: List[str]
) -> Dict:
    """
    Build JSON structure for episode data.

    Args:
        video_info: Dict with 'url', 'title', 'date'
        cleaned_text: Full cleaned transcript
        chunks: List of text chunks

    Returns:
        Episode data dict ready for JSON serialization
    """
    video_id = extract_video_id(video_info['url'])

    # Create episode ID from video ID or fallback to title + date slug
    if video_id:
        episode_id = video_id
    else:
        # Slugify title + date
        slug = f"{video_info['title']}_{video_info['date']}"
        slug = re.sub(r'[^\w\s-]', '', slug.lower())
        slug = re.sub(r'[-\s]+', '-', slug)
        episode_id = slug

    chunk_data = []
    for idx, chunk_text in enumerate(chunks):
        chunk_data.append({
            'chunk_index': idx,
            'text': chunk_text,
            'approx_word_count': len(chunk_text.split())
        })

    return {
        'episode_id': episode_id,
        'youtube_url': video_info['url'],
        'title': video_info['title'],
        'date': video_info['date'],
        'raw_text_length': len(cleaned_text),
        'num_chunks': len(chunks),
        'chunks': chunk_data
    }


def save_episode_json(episode_data: Dict, output_dir: Path) -> None:
    """
    Save episode data to JSON file.

    Args:
        episode_data: Episode data dict
        output_dir: Directory to save JSON file
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / f"{episode_data['episode_id']}.json"

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(episode_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Saved episode JSON: {output_file}")


def process_video(
    video_info: Dict[str, str],
    temp_dir: Path,
    output_dir: Path,
    use_youtube_subtitles: bool,
    whisper_model: str,
    target_word_count: int,
    overlap_words: int
) -> bool:
    """
    Process a single video end-to-end.

    Args:
        video_info: Dict with 'url', 'title', 'date'
        temp_dir: Temporary directory for downloads
        output_dir: Output directory for JSON files
        use_youtube_subtitles: Whether to try YouTube subtitles
        whisper_model: Whisper model name
        target_word_count: Target words per chunk
        overlap_words: Overlap between chunks

    Returns:
        True if successful, False otherwise
    """
    try:
        logger.info(f"Processing: {video_info['title']} ({video_info['date']})")

        # Download subtitles or audio
        download_result = download_subtitles_or_audio(
            video_info,
            temp_dir,
            use_youtube_subtitles
        )

        # Get transcript
        if download_result['type'] == 'subtitles':
            logger.info("Extracting text from subtitles")
            raw_text = parse_subtitles(Path(download_result['path']))
        else:
            logger.info("Transcribing audio with Whisper")
            raw_text = transcribe_audio_with_whisper(
                Path(download_result['path']),
                whisper_model
            )

        # Clean transcript
        cleaned_text = clean_transcript_text(raw_text)
        logger.info(f"Cleaned transcript length: {len(cleaned_text)} characters")

        # Chunk text
        chunks = split_into_chunks(cleaned_text, target_word_count, overlap_words)
        logger.info(f"Created {len(chunks)} chunks")

        # Build episode JSON
        episode_data = build_episode_json(video_info, cleaned_text, chunks)

        # Save JSON
        save_episode_json(episode_data, output_dir)

        logger.info(f"Successfully processed: {video_info['title']}")
        return True

    except Exception as e:
        logger.error(f"Failed to process {video_info['title']}: {e}", exc_info=True)
        return False


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Process Radu Banciu YouTube videos into transcript chunks'
    )
    parser.add_argument(
        '--input-file',
        required=True,
        help='Path to input CSV file with columns: url, title, date'
    )
    parser.add_argument(
        '--output-dir',
        required=True,
        help='Directory to save episode JSON files'
    )
    parser.add_argument(
        '--temp-dir',
        default='temp',
        help='Temporary directory for downloads (default: temp)'
    )
    parser.add_argument(
        '--max-videos',
        type=int,
        help='Maximum number of videos to process'
    )
    parser.add_argument(
        '--use-youtube-subtitles',
        action='store_true',
        default=True,
        help='Try YouTube subtitles before Whisper (default: True)'
    )
    parser.add_argument(
        '--whisper-model',
        default='medium',
        choices=['tiny', 'base', 'small', 'medium', 'large'],
        help='Whisper model to use for transcription (default: medium)'
    )
    parser.add_argument(
        '--target-word-count',
        type=int,
        default=1200,
        help='Target words per chunk (default: 1200)'
    )
    parser.add_argument(
        '--overlap-words',
        type=int,
        default=100,
        help='Words to overlap between chunks (default: 100)'
    )

    args = parser.parse_args()

    # Setup paths
    output_dir = Path(args.output_dir)
    temp_dir = Path(args.temp_dir)

    # Load video list
    try:
        videos = load_video_list(args.input_file)
    except Exception as e:
        logger.error(f"Failed to load video list: {e}")
        sys.exit(1)

    if not videos:
        logger.error("No videos found in input file")
        sys.exit(1)

    # Limit videos if requested
    if args.max_videos:
        videos = videos[:args.max_videos]
        logger.info(f"Processing first {len(videos)} videos")

    # Process each video
    success_count = 0
    failure_count = 0

    for video_info in videos:
        success = process_video(
            video_info,
            temp_dir,
            output_dir,
            args.use_youtube_subtitles,
            args.whisper_model,
            args.target_word_count,
            args.overlap_words
        )

        if success:
            success_count += 1
        else:
            failure_count += 1

    # Summary
    logger.info("=" * 60)
    logger.info(f"Processing complete!")
    logger.info(f"  Successful: {success_count}")
    logger.info(f"  Failed: {failure_count}")
    logger.info(f"  Total: {len(videos)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
