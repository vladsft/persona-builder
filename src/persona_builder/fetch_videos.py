#!/usr/bin/env python3
"""
Fetch Radu Banciu YouTube videos by date and generate a CSV file.
"""

import argparse
import csv
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import yt_dlp

from .paths import DEFAULT_VIDEO_LIST, ensure_repo_layout

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

ROMANIAN_MONTHS = {
    "ianuarie": 1,
    "februarie": 2,
    "martie": 3,
    "aprilie": 4,
    "mai": 5,
    "iunie": 6,
    "iulie": 7,
    "august": 8,
    "septembrie": 9,
    "octombrie": 10,
    "noiembrie": 11,
    "decembrie": 12,
}

DEFAULT_DATES = [
    "5 Decembrie",
    "27 Noiembrie",
    "25 Noiembrie",
    "17 Noiembrie",
    "11 Noiembrie",
    "3 Noiembrie",
    "31 Octombrie",
    "29 Octombrie",
    "22 Octombrie",
    "16 Octombrie",
    "14 Octombrie",
    "11 Octombrie",
    "9 Octombrie",
    "17 Septembrie",
    "31 ianuarie",
    "27 ianuarie",
    "21 Ianuarie",
    "20 Ianuarie",
    "19 Ianuarie",
    "7 Ianuarie",
    "6 Ianuarie",
    "9 Februarie",
    "12 Februarie",
    "24 Februarie",
    "4 Martie",
    "5 Martie",
    "6 Martie",
    "3 Martie",
]


def parse_romanian_date(date_str: str, year: int = 2024) -> Optional[str]:
    try:
        parts = date_str.strip().split()
        if len(parts) != 2:
            return None

        day_str, month_str = parts
        day = int(day_str)
        month_str = month_str.lower()

        if month_str == "ocrombrie":
            month_str = "octombrie"

        if month_str not in ROMANIAN_MONTHS:
            logger.warning(f"Unknown month: {month_str}")
            return None

        date_obj = datetime(year, ROMANIAN_MONTHS[month_str], day)
        return date_obj.strftime("%Y-%m-%d")
    except (ValueError, IndexError) as exc:
        logger.error(f"Failed to parse date '{date_str}': {exc}")
        return None


def search_youtube_for_video(search_query: str, max_results: int = 5) -> List[Dict[str, str]]:
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "force_generic_extractor": False,
    }

    results = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(f"ytsearch{max_results}:{search_query}", download=False)
            if search_results and "entries" in search_results:
                for entry in search_results["entries"]:
                    if entry:
                        results.append(
                            {
                                "url": f"https://www.youtube.com/watch?v={entry['id']}",
                                "title": entry.get("title", "Unknown"),
                                "upload_date": entry.get("upload_date", ""),
                            }
                        )
    except Exception as exc:
        logger.error(f"Search failed for '{search_query}': {exc}")

    return results


def find_video_for_date(date_str: str, year: int = 2024) -> Optional[Dict[str, str]]:
    logger.info(f"Searching for video: {date_str}")
    standard_date = parse_romanian_date(date_str, year)
    if not standard_date:
        logger.error(f"Could not parse date: {date_str}")
        return None

    search_patterns = [
        f"Prea Mult Banciu - {date_str}",
        f"PreaMultBanciu - {date_str}",
        f"Prea Mult Banciu {date_str}",
        f"PreaMultBanciu {date_str}",
    ]

    for pattern in search_patterns:
        results = search_youtube_for_video(pattern, max_results=3)
        for result in results:
            title = result["title"]
            if date_str.lower() in title.lower():
                logger.info(f"Found video: {title}")
                return {
                    "url": result["url"],
                    "title": title,
                    "date": standard_date,
                }

    logger.warning(f"No video found for: {date_str}")
    return None


def fetch_videos_for_dates(dates: List[str], year: int = 2024) -> List[Dict[str, str]]:
    videos = []
    for date_str in dates:
        video = find_video_for_date(date_str, year)
        if video:
            videos.append(video)
        else:
            logger.warning(f"Skipping {date_str} - not found")
    return videos


def save_videos_to_csv(videos: List[Dict[str, str]], output_file: str | Path) -> None:
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["url", "title", "date"])
        writer.writeheader()
        writer.writerows(videos)
    logger.info(f"Saved {len(videos)} videos to {output_path}")


def main() -> None:
    ensure_repo_layout()

    parser = argparse.ArgumentParser(description="Fetch Radu Banciu YouTube videos by date")
    parser.add_argument(
        "--output-file",
        default=str(DEFAULT_VIDEO_LIST),
        help=f"Output CSV file path (default: {DEFAULT_VIDEO_LIST})",
    )
    parser.add_argument("--year", type=int, default=2024, help="Year for the dates (default: 2024)")
    parser.add_argument(
        "--dates",
        nargs="+",
        help='Romanian dates to search for (e.g., "5 Decembrie" "27 Noiembrie")',
    )
    parser.add_argument("--use-default-dates", action="store_true", help="Use the predefined list of dates")

    args = parser.parse_args()

    if args.dates:
        dates_to_search = args.dates
    elif args.use_default_dates:
        dates_to_search = DEFAULT_DATES
    else:
        logger.error("Specify either --dates or --use-default-dates")
        sys.exit(1)

    videos = fetch_videos_for_dates(dates_to_search, args.year)
    if not videos:
        logger.error("No videos found")
        sys.exit(1)

    save_videos_to_csv(videos, args.output_file)


if __name__ == "__main__":
    main()

