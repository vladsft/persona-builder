#!/usr/bin/env python3
"""
Fetch Radu Banciu YouTube videos by date and generate a CSV file.

Reads show dates from a text file (data/input/show_dates.txt by default),
searches YouTube for matching videos, and appends new finds to the video CSV.
Supports both "Prea Mult Banciu" (politic) and "iAM Banciu" (sport) shows.
"""

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import yt_dlp

from .paths import DEFAULT_SHOW_DATES, DEFAULT_VIDEO_LIST, ensure_repo_layout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ROMANIAN_MONTHS = {
    "ianuarie": 1, "februarie": 2, "martie": 3, "aprilie": 4,
    "mai": 5, "iunie": 6, "iulie": 7, "august": 8,
    "septembrie": 9, "octombrie": 10, "noiembrie": 11, "decembrie": 12,
}

# YouTube search patterns per show type — {date} is replaced with e.g. "5 Decembrie"
SHOW_SEARCH_PATTERNS: dict[str, list[str]] = {
    "politic": [
        "Prea Mult Banciu - {date}",
        "PreaMultBanciu - {date}",
        "Prea Mult Banciu {date}",
        "PreaMultBanciu {date}",
    ],
    "sport": [
        "iAM Banciu - {date}",
        "iAMBanciu - {date}",
        "iAM Banciu {date}",
        "iam Banciu {date}",
    ],
}

# Substrings that must appear in the video title to confirm it's the right show
SHOW_TITLE_MARKERS: dict[str, list[str]] = {
    "politic": ["prea mult banciu", "preamultbanciu"],
    "sport": ["iam banciu", "iambanciu", "i am banciu"],
}


def parse_romanian_date(date_str: str, default_year: int = 2025) -> str | None:
    """Parse '5 Decembrie' or '5 Decembrie 2025' into an ISO date string."""
    try:
        parts = date_str.strip().split()
        if len(parts) == 3:
            day_str, month_str, year_str = parts
            year = int(year_str)
        elif len(parts) == 2:
            day_str, month_str = parts
            year = default_year
        else:
            return None

        day = int(day_str)
        month_key = month_str.lower()

        if month_key == "ocrombrie":
            month_key = "octombrie"

        if month_key not in ROMANIAN_MONTHS:
            logger.warning(f"Unknown month: {month_key}")
            return None

        return datetime(year, ROMANIAN_MONTHS[month_key], day).strftime("%Y-%m-%d")
    except (ValueError, IndexError) as exc:
        logger.error(f"Failed to parse date '{date_str}': {exc}")
        return None


def parse_show_dates_file(dates_file: Path) -> list[dict[str, Any]]:
    """Parse show_dates.txt into a list of {date_str, year, show_type} dicts.

    File format::

        # politic
        17 Septembrie 2025
        5 Decembrie 2025

        # sport
        24 Februarie 2026
    """
    if not dates_file.exists():
        logger.error(f"Dates file not found: {dates_file}")
        return []

    entries: list[dict[str, Any]] = []
    current_type: str | None = None

    for line in dates_file.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        # Section header
        if stripped.startswith("#"):
            label = stripped.lstrip("#").strip().lower()
            if label in SHOW_SEARCH_PATTERNS:
                current_type = label
            else:
                logger.warning(
                    f"Unknown show type '{label}', expected one of: {list(SHOW_SEARCH_PATTERNS)}"
                )
                current_type = None
            continue

        if current_type is None:
            continue

        # Parse "DD Luna YYYY" or "DD Luna"
        parts = stripped.split()
        if len(parts) == 3:
            date_str = f"{parts[0]} {parts[1]}"
            try:
                year = int(parts[2])
            except ValueError:
                logger.warning(f"Bad year in '{stripped}', skipping")
                continue
        elif len(parts) == 2:
            date_str = stripped
            year = 2025
        else:
            logger.warning(f"Bad date format '{stripped}', expected 'DD Luna YYYY'")
            continue

        entries.append({
            "date_str": date_str,
            "year": year,
            "show_type": current_type,
        })

    return entries


def _infer_show_type(title: str) -> str:
    """Guess show type from a video title already in the CSV."""
    title_lower = title.lower()
    for marker in SHOW_TITLE_MARKERS.get("sport", []):
        if marker in title_lower:
            return "sport"
    return "politic"


def search_youtube_for_video(search_query: str, max_results: int = 5) -> list[dict[str, str]]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "force_generic_extractor": False,
    }

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(
                f"ytsearch{max_results}:{search_query}", download=False,
            )
            if search_results and "entries" in search_results:
                for entry in search_results["entries"]:
                    if entry:
                        results.append({
                            "url": f"https://www.youtube.com/watch?v={entry['id']}",
                            "title": entry.get("title", "Unknown"),
                        })
    except Exception as exc:
        logger.error(f"Search failed for '{search_query}': {exc}")

    return results


def find_video_for_date(
    date_str: str,
    year: int,
    show_type: str,
) -> dict[str, str] | None:
    """Search YouTube for a specific show date and return the matching video."""
    iso_date = parse_romanian_date(date_str, year)
    if not iso_date:
        logger.error(f"Could not parse date: {date_str} {year}")
        return None

    logger.info(f"Searching [{show_type}]: {date_str} {year}")

    patterns = SHOW_SEARCH_PATTERNS.get(show_type, SHOW_SEARCH_PATTERNS["politic"])
    title_markers = SHOW_TITLE_MARKERS.get(show_type, SHOW_TITLE_MARKERS["politic"])

    for pattern in patterns:
        query = pattern.format(date=date_str)
        results = search_youtube_for_video(query, max_results=3)
        for result in results:
            title_lower = result["title"].lower()
            # Must contain both the date AND a show-name marker
            if date_str.lower() in title_lower and any(m in title_lower for m in title_markers):
                logger.info(f"  Found: {result['title']}")
                return {
                    "url": result["url"],
                    "title": result["title"],
                    "date": iso_date,
                }

    logger.warning(f"  No video found for [{show_type}] {date_str} {year}")
    return None


def load_existing_csv(csv_path: Path) -> list[dict[str, str]]:
    """Load existing video CSV, returning empty list if file doesn't exist."""
    if not csv_path.exists():
        return []
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append({
                "url": row["url"].strip(),
                "title": row["title"].strip(),
                "date": row["date"].strip(),
            })
    return rows


def save_videos_to_csv(videos: list[dict[str, str]], output_file: str | Path) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "title", "date"])
        writer.writeheader()
        for video in sorted(videos, key=lambda v: v["date"]):
            writer.writerow(video)
    logger.info(f"Saved {len(videos)} videos to {output_path}")


def main() -> None:
    ensure_repo_layout()

    parser = argparse.ArgumentParser(
        description="Fetch Radu Banciu YouTube videos by date",
    )
    parser.add_argument(
        "--dates-file",
        default=str(DEFAULT_SHOW_DATES),
        help=f"Path to show dates file (default: {DEFAULT_SHOW_DATES})",
    )
    parser.add_argument(
        "--output-file",
        default=str(DEFAULT_VIDEO_LIST),
        help=f"Output CSV file path (default: {DEFAULT_VIDEO_LIST})",
    )
    parser.add_argument(
        "--dates",
        nargs="+",
        help='Ad-hoc Romanian dates to search as politic show (e.g. "5 Decembrie")',
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2025,
        help="Default year for ad-hoc --dates without explicit year (default: 2025)",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Re-fetch all dates, ignoring existing CSV",
    )

    args = parser.parse_args()
    output_path = Path(args.output_file)

    # Determine dates to process
    if args.dates:
        entries = [
            {"date_str": d, "year": args.year, "show_type": "politic"}
            for d in args.dates
        ]
    else:
        entries = parse_show_dates_file(Path(args.dates_file))
        if not entries:
            logger.error("No dates found. Check your dates file.")
            sys.exit(1)

    # Load existing CSV for incremental mode
    if args.full_refresh:
        existing = []
    else:
        existing = load_existing_csv(output_path)

    existing_pairs = {
        (row["date"], _infer_show_type(row["title"]))
        for row in existing
    }

    # Filter to only new (date, show_type) pairs
    new_entries = []
    for entry in entries:
        iso = parse_romanian_date(entry["date_str"], entry["year"])
        if iso and (iso, entry["show_type"]) not in existing_pairs:
            new_entries.append(entry)

    if not new_entries:
        logger.info(
            f"All {len(entries)} date(s) already in CSV. Nothing to fetch."
        )
        return

    logger.info(
        f"{len(new_entries)} new date(s) to fetch, {len(existing)} already in CSV"
    )

    # Fetch new videos from YouTube
    new_videos = []
    for entry in new_entries:
        video = find_video_for_date(
            entry["date_str"], entry["year"], entry["show_type"],
        )
        if video:
            new_videos.append(video)

    if not new_videos:
        logger.warning("No new videos found on YouTube")
        return

    # Merge with existing and save (sorted by date)
    all_videos = existing + new_videos
    save_videos_to_csv(all_videos, output_path)
    logger.info(f"Added {len(new_videos)} new video(s). Total: {len(all_videos)}")


if __name__ == "__main__":
    main()
