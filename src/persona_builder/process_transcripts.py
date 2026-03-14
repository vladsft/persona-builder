#!/usr/bin/env python3
"""
Process Radu Banciu YouTube videos into cleaned transcript chunks.
"""

import argparse
import csv
import json
import logging
import os
import re
import shutil
import sys
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import parse_qs, urlparse

import yt_dlp

from .paths import DEFAULT_OUTPUT_DIR, DEFAULT_TEMP_DIR, DEFAULT_VIDEO_LIST, ensure_repo_layout

try:
    import whisper
except ImportError:
    whisper = None


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

MUSIC_MARKER_RE = re.compile(r"\[(?:music|muzic[ăa]|applause|laughter|r[âa]sete)\]", re.IGNORECASE)
LEADING_CUE_MARKER_RE = re.compile(r"^(?:>>\s*)+")
HTML_TAG_RE = re.compile(r"<[^>]+>")
WORD_RE = re.compile(r"\b[\wĂÂÎȘȚăâîșț'-]+\b", re.UNICODE)
FILLER_ONLY_RE = re.compile(r"^(?:a+h+|ah+|h+|hm+|mmm+|mm+|uh+|oh+|eh+|ă+)\.?!?$", re.IGNORECASE)
ROMANIAN_MARKERS = {
    "și", "sa", "să", "în", "la", "de", "că", "nu", "ce", "se", "este", "sunt",
    "un", "o", "pe", "cu", "pentru", "noi", "vă", "va", "dar", "din", "tot",
}


def _strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _normalize_word(word: str) -> str:
    cleaned = _strip_accents(word.lower())
    return re.sub(r"[^\w]+", "", cleaned)


def _looks_like_romanian_speech(text: str) -> bool:
    words = [_normalize_word(word) for word in WORD_RE.findall(text)]
    words = [word for word in words if word]
    if len(words) < 3:
        return False

    marker_hits = sum(1 for word in words if word in ROMANIAN_MARKERS)
    has_diacritics = bool(re.search(r"[ăâîșțĂÂÎȘȚ]", text))
    return marker_hits >= 2 or has_diacritics


def _clean_subtitle_cue_text(text: str) -> str:
    text = text.replace("\ufeff", " ")
    text = HTML_TAG_RE.sub(" ", text)
    text = LEADING_CUE_MARKER_RE.sub("", text)
    text = text.replace(">>", " ")
    text = MUSIC_MARKER_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip(" -\t\r\n")
    return text.strip()


def _should_skip_cue(text: str) -> bool:
    if not text:
        return True
    if FILLER_ONLY_RE.match(text):
        return True

    words = WORD_RE.findall(text)
    if not words:
        return True
    if len(words) == 1 and len(words[0]) <= 2:
        return True
    return False


def _drop_leading_overlap(previous_text: str, current_text: str, max_words: int = 12) -> str:
    previous_words = previous_text.split()
    current_words = current_text.split()
    max_overlap = min(len(previous_words), len(current_words), max_words)

    for overlap_size in range(max_overlap, 0, -1):
        previous_slice = [_normalize_word(word) for word in previous_words[-overlap_size:]]
        current_slice = [_normalize_word(word) for word in current_words[:overlap_size]]
        if previous_slice == current_slice:
            return " ".join(current_words[overlap_size:]).strip()

    return current_text


def _parse_subtitle_cues(subtitle_path: Path) -> List[str]:
    content = subtitle_path.read_text(encoding="utf-8")
    blocks = re.split(r"\n\s*\n", content.strip())

    cues: List[str] = []
    speech_started = False

    for block in blocks:
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines or "-->" not in lines[0]:
            continue

        cue_text = _clean_subtitle_cue_text(" ".join(lines[1:]))
        if _should_skip_cue(cue_text):
            continue

        if not speech_started:
            if not _looks_like_romanian_speech(cue_text):
                continue
            speech_started = True

        if cues:
            cue_text = _drop_leading_overlap(cues[-1], cue_text)
            if not cue_text:
                continue
            if _normalize_word(cue_text) == _normalize_word(cues[-1]):
                continue

        cues.append(cue_text)

    return cues


def load_video_list(input_file: str | Path) -> List[Dict[str, str]]:
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    videos = []
    with open(input_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "url" not in row or "title" not in row or "date" not in row:
                logger.warning(f"Skipping row with missing fields: {row}")
                continue
            videos.append(
                {
                    "url": row["url"].strip(),
                    "title": row["title"].strip(),
                    "date": row["date"].strip(),
                }
            )

    logger.info(f"Loaded {len(videos)} videos from {input_path}")
    return videos


def extract_video_id(url: str) -> Optional[str]:
    parsed = urlparse(url)
    if parsed.hostname == "youtu.be":
        return parsed.path[1:]
    if parsed.hostname in ("www.youtube.com", "youtube.com"):
        if parsed.path == "/watch":
            query = parse_qs(parsed.query)
            return query.get("v", [None])[0]
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/")[2]
        if parsed.path.startswith("/v/"):
            return parsed.path.split("/")[2]
    return None


def ensure_ffmpeg_available() -> Optional[str]:
    ffmpeg_path = shutil.which("ffmpeg")
    ffprobe_path = shutil.which("ffprobe")
    if ffmpeg_path and ffprobe_path:
        return ffmpeg_path

    try:
        import imageio_ffmpeg
    except ImportError:
        return None

    ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()
    ffmpeg_dir = str(Path(ffmpeg_path).parent)
    current_path = os.environ.get("PATH", "")
    if ffmpeg_dir not in current_path.split(os.pathsep):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path

    if shutil.which("ffmpeg") and shutil.which("ffprobe"):
        logger.info(f"Using bundled ffmpeg from {ffmpeg_dir}")
        return shutil.which("ffmpeg")

    return None


def download_subtitles_or_audio(
    video_info: Dict[str, str],
    temp_dir: Path,
    use_youtube_subtitles: bool = True,
) -> Dict[str, str]:
    video_id = extract_video_id(video_info["url"])
    if not video_id:
        raise ValueError(f"Could not extract video ID from URL: {video_info['url']}")

    temp_dir.mkdir(parents=True, exist_ok=True)

    if use_youtube_subtitles:
        subtitle_path = temp_dir / f"{video_id}.ro.srt"
        ydl_opts_subs = {
            "writesubtitles": True,
            "writeautomaticsub": True,
            "subtitleslangs": ["ro"],
            "subtitlesformat": "srt",
            "skip_download": True,
            "outtmpl": str(temp_dir / video_id),
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts_subs) as ydl:
                ydl.download([video_info["url"]])
            if subtitle_path.exists():
                logger.info(f"Downloaded Romanian subtitles for {video_id}")
                return {"type": "subtitles", "path": str(subtitle_path)}
        except Exception as exc:
            logger.warning(f"Failed to download subtitles for {video_id}: {exc}")

    ffmpeg_path = ensure_ffmpeg_available()
    audio_path = temp_dir / f"{video_id}.m4a"
    ydl_opts_audio = {
        "format": "bestaudio/best",
        "outtmpl": str(temp_dir / f"{video_id}.%(ext)s"),
        "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "m4a"}],
        "quiet": True,
        "no_warnings": True,
    }
    if ffmpeg_path:
        ydl_opts_audio["ffmpeg_location"] = str(Path(ffmpeg_path).parent)

    try:
        with yt_dlp.YoutubeDL(ydl_opts_audio) as ydl:
            ydl.download([video_info["url"]])
        logger.info(f"Downloaded audio for {video_id}")
        return {"type": "audio", "path": str(audio_path)}
    except Exception as exc:
        raise RuntimeError(f"Failed to download audio for {video_id}: {exc}") from exc


def parse_subtitles(subtitle_path: Path) -> str:
    return "\n".join(_parse_subtitle_cues(subtitle_path))


def transcribe_audio_with_whisper(audio_path: Path, model_name: str = "medium") -> str:
    if whisper is None:
        raise RuntimeError("Whisper is not installed. Install with: pip install openai-whisper")

    ensure_ffmpeg_available()
    logger.info(f"Loading Whisper model: {model_name}")
    model = whisper.load_model(model_name)

    logger.info(f"Transcribing audio: {audio_path}")
    result = model.transcribe(str(audio_path), language="ro", verbose=False)
    return result["text"]


def clean_transcript_text(raw_text: str) -> str:
    text = raw_text
    placeholders = [
        r"\[Music\]", r"\[Applause\]", r"\[Laughter\]",
        r"\[music\]", r"\[applause\]", r"\[laughter\]",
        r"\[MUSIC\]", r"\[APPLAUSE\]", r"\[LAUGHTER\]",
        r"\[muzică\]", r"\[Muzică\]", r"\[MUZICĂ\]",
        r"\[râsete\]", r"\[Râsete\]", r"\[RÂSETE\]",
    ]
    for placeholder in placeholders:
        text = re.sub(placeholder, "", text)

    text = text.replace(">>", " ")
    text = HTML_TAG_RE.sub(" ", text)
    text = re.sub(r"(?m)^\s*(?:a+h+|ah+|h+|hm+|mmm+|mm+|uh+|oh+|eh+|ă+)\.?!?\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r" +", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n\n+", "\n\n", text)
    return text.strip()


def split_into_chunks(clean_text: str, target_word_count: int = 1200, overlap_words: int = 100) -> List[str]:
    sentence_pattern = r"(?<=[.!?])\s+"
    sentences = [sentence.strip() for sentence in re.split(sentence_pattern, clean_text) if sentence.strip()]

    if len(sentences) <= 1:
        line_segments = [line.strip() for line in re.split(r"\n+", clean_text) if line.strip()]
        if line_segments:
            sentences = line_segments

    if len(sentences) <= 1 and len(clean_text.split()) > target_word_count:
        words = clean_text.split()
        sentences = []
        for i in range(0, len(words), target_word_count - overlap_words):
            sentences.append(" ".join(words[i:i + target_word_count]))
        return [sentence for sentence in sentences if sentence.strip()]

    chunks = []
    current_chunk = []
    current_word_count = 0

    for sentence in sentences:
        sentence_words = sentence.split()
        sentence_word_count = len(sentence_words)
        if current_word_count + sentence_word_count > target_word_count and current_chunk:
            chunks.append(" ".join(current_chunk))
            if overlap_words > 0:
                overlap_sentences = []
                overlap_count = 0
                for previous_sentence in reversed(current_chunk):
                    overlap_sentences.insert(0, previous_sentence)
                    overlap_count += len(previous_sentence.split())
                    if overlap_count >= overlap_words:
                        break
                current_chunk = overlap_sentences
                current_word_count = overlap_count
            else:
                current_chunk = []
                current_word_count = 0

        current_chunk.append(sentence)
        current_word_count += sentence_word_count

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def analyze_corpus(output_dir: Path) -> Dict[str, object]:
    episode_paths = sorted(output_dir.glob("*.json"))
    suspect_starts = []
    noise_counter: Counter[str] = Counter()
    chunk_word_counts: List[int] = []
    per_episode_stats: List[Dict[str, object]] = []

    for path in episode_paths:
        with open(path, encoding="utf-8") as f:
            episode = json.load(f)

        episode_chunks = episode.get("chunks", [])
        per_episode_stats.append(
            {
                "episode_id": episode.get("episode_id"),
                "title": episode.get("title"),
                "num_chunks": len(episode_chunks),
            }
        )

        for chunk in episode_chunks:
            text = chunk.get("text", "").strip()
            chunk_word_counts.append(len(text.split()))
            if re.search(r">>|\b(?:ah|h|hm|mmm)\b", text, re.IGNORECASE):
                for token in re.findall(r">>|\b(?:ah|h|hm|mmm)\b", text, re.IGNORECASE):
                    noise_counter[token.lower()] += 1
            if text and not re.match(r'^[A-ZĂÂÎȘȚ0-9"„(]', text):
                suspect_starts.append(
                    {
                        "episode_id": episode.get("episode_id"),
                        "chunk_index": chunk.get("chunk_index"),
                        "start": text[:120],
                    }
                )

    return {
        "episode_count": len(episode_paths),
        "chunk_count": len(chunk_word_counts),
        "chunk_word_count_min": min(chunk_word_counts) if chunk_word_counts else 0,
        "chunk_word_count_max": max(chunk_word_counts) if chunk_word_counts else 0,
        "chunk_word_count_avg": (sum(chunk_word_counts) / len(chunk_word_counts)) if chunk_word_counts else 0,
        "noise_tokens": dict(noise_counter.most_common()),
        "suspect_starts": suspect_starts[:25],
        "per_episode_stats": per_episode_stats,
    }


def print_corpus_qa_report(output_dir: Path) -> None:
    report = analyze_corpus(output_dir)
    logger.info("Corpus QA report")
    logger.info(f"  Episodes: {report['episode_count']}")
    logger.info(f"  Chunks: {report['chunk_count']}")
    logger.info(
        "  Chunk words: min=%s avg=%.1f max=%s",
        report["chunk_word_count_min"],
        report["chunk_word_count_avg"],
        report["chunk_word_count_max"],
    )
    if report["noise_tokens"]:
        logger.info(f"  Noise tokens still present: {report['noise_tokens']}")
    else:
        logger.info("  Noise tokens still present: none")

    if report["suspect_starts"]:
        logger.info("  Suspect chunk starts:")
        for item in report["suspect_starts"][:10]:
            logger.info("    %s chunk %s: %s", item["episode_id"], item["chunk_index"], item["start"])
    else:
        logger.info("  Suspect chunk starts: none")


def build_episode_json(video_info: Dict[str, str], cleaned_text: str, chunks: List[str]) -> Dict:
    video_id = extract_video_id(video_info["url"])
    if video_id:
        episode_id = video_id
    else:
        slug = f"{video_info['title']}_{video_info['date']}"
        slug = re.sub(r"[^\w\s-]", "", slug.lower())
        slug = re.sub(r"[-\s]+", "-", slug)
        episode_id = slug

    return {
        "episode_id": episode_id,
        "youtube_url": video_info["url"],
        "title": video_info["title"],
        "date": video_info["date"],
        "raw_text_length": len(cleaned_text),
        "num_chunks": len(chunks),
        "chunks": [
            {
                "chunk_index": idx,
                "text": chunk_text,
                "approx_word_count": len(chunk_text.split()),
            }
            for idx, chunk_text in enumerate(chunks)
        ],
    }


def save_episode_json(episode_data: Dict, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{episode_data['episode_id']}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(episode_data, f, ensure_ascii=False, indent=2)
    logger.info(f"Saved episode JSON: {output_file}")


def process_video(
    video_info: Dict[str, str],
    temp_dir: Path,
    output_dir: Path,
    use_youtube_subtitles: bool,
    whisper_model: str,
    target_word_count: int,
    overlap_words: int,
) -> bool:
    try:
        logger.info(f"Processing: {video_info['title']} ({video_info['date']})")
        download_result = download_subtitles_or_audio(video_info, temp_dir, use_youtube_subtitles)
        if download_result["type"] == "subtitles":
            logger.info("Extracting text from subtitles")
            raw_text = parse_subtitles(Path(download_result["path"]))
        else:
            logger.info("Transcribing audio with Whisper")
            raw_text = transcribe_audio_with_whisper(Path(download_result["path"]), whisper_model)

        cleaned_text = clean_transcript_text(raw_text)
        logger.info(f"Cleaned transcript length: {len(cleaned_text)} characters")
        chunks = split_into_chunks(cleaned_text, target_word_count, overlap_words)
        logger.info(f"Created {len(chunks)} chunks")
        episode_data = build_episode_json(video_info, cleaned_text, chunks)
        save_episode_json(episode_data, output_dir)
        logger.info(f"Successfully processed: {video_info['title']}")
        return True
    except Exception as exc:
        logger.error(f"Failed to process {video_info['title']}: {exc}", exc_info=True)
        return False


def main() -> None:
    ensure_repo_layout()

    parser = argparse.ArgumentParser(description="Process Radu Banciu YouTube videos into transcript chunks")
    parser.add_argument(
        "--input-file",
        default=str(DEFAULT_VIDEO_LIST),
        help=f"Path to input CSV file with columns: url, title, date (default: {DEFAULT_VIDEO_LIST})",
    )
    parser.add_argument(
        "--output-dir",
        default=str(DEFAULT_OUTPUT_DIR),
        help=f"Directory to save episode JSON files (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--temp-dir",
        default=str(DEFAULT_TEMP_DIR),
        help=f"Temporary directory for downloads (default: {DEFAULT_TEMP_DIR})",
    )
    parser.add_argument("--max-videos", type=int, help="Maximum number of videos to process")
    parser.add_argument("--use-youtube-subtitles", action="store_true", default=True, help="Try YouTube subtitles before Whisper (default: True)")
    parser.add_argument("--whisper-model", default="medium", choices=["tiny", "base", "small", "medium", "large"], help="Whisper model to use for transcription (default: medium)")
    parser.add_argument("--target-word-count", type=int, default=1200, help="Target words per chunk (default: 1200)")
    parser.add_argument("--overlap-words", type=int, default=100, help="Words to overlap between chunks (default: 100)")
    parser.add_argument("--qa-only", action="store_true", help="Only run a QA report against output-dir and exit")
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    temp_dir = Path(args.temp_dir)

    if args.qa_only:
        if not output_dir.exists():
            logger.error(f"Output directory not found: {output_dir}")
            sys.exit(1)
        print_corpus_qa_report(output_dir)
        return

    try:
        videos = load_video_list(args.input_file)
    except Exception as exc:
        logger.error(f"Failed to load video list: {exc}")
        sys.exit(1)

    if not videos:
        logger.error("No videos found in input file")
        sys.exit(1)

    if args.max_videos:
        videos = videos[:args.max_videos]
        logger.info(f"Processing first {len(videos)} videos")

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
            args.overlap_words,
        )
        if success:
            success_count += 1
        else:
            failure_count += 1

    logger.info("=" * 60)
    logger.info("Processing complete!")
    logger.info(f"  Successful: {success_count}")
    logger.info(f"  Failed: {failure_count}")
    logger.info(f"  Total: {len(videos)}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

