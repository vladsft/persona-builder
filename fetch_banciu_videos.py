#!/usr/bin/env python3
"""
Fetch Radu Banciu YouTube videos by date and generate a CSV file.

This script searches for videos with titles matching:
- "Prea Mult Banciu - <date> | <title>"
- "PreaMultBanciu - <date> | <title>"

where <date> is in Romanian format like "23 Septembrie"
"""

import argparse
import csv
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

import yt_dlp


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Romanian month names to numbers
ROMANIAN_MONTHS = {
    'ianuarie': 1,
    'februarie': 2,
    'martie': 3,
    'aprilie': 4,
    'mai': 5,
    'iunie': 6,
    'iulie': 7,
    'august': 8,
    'septembrie': 9,
    'octombrie': 10,
    'noiembrie': 11,
    'decembrie': 12,
}


def parse_romanian_date(date_str: str, year: int = 2024) -> Optional[str]:
    """
    Parse Romanian date string to YYYY-MM-DD format.

    Args:
        date_str: Date string like "23 Septembrie" or "5 Decembrie"
        year: Year to use (default: 2024)

    Returns:
        Date in YYYY-MM-DD format or None if parsing fails
    """
    try:
        # Split into day and month
        parts = date_str.strip().split()
        if len(parts) != 2:
            return None

        day_str, month_str = parts
        day = int(day_str)
        month_str = month_str.lower()

        # Handle common typo "Ocrombrie" -> "Octombrie"
        if month_str == 'ocrombrie':
            month_str = 'octombrie'

        if month_str not in ROMANIAN_MONTHS:
            logger.warning(f"Unknown month: {month_str}")
            return None

        month = ROMANIAN_MONTHS[month_str]

        # Create date
        date_obj = datetime(year, month, day)
        return date_obj.strftime('%Y-%m-%d')

    except (ValueError, IndexError) as e:
        logger.error(f"Failed to parse date '{date_str}': {e}")
        return None


def search_youtube_for_video(
    search_query: str,
    max_results: int = 5
) -> List[Dict[str, str]]:
    """
    Search YouTube for videos matching a query.

    Args:
        search_query: Search query string
        max_results: Maximum number of results to return

    Returns:
        List of dicts with 'url', 'title', 'upload_date'
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'force_generic_extractor': False,
    }

    results = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            search_results = ydl.extract_info(
                f"ytsearch{max_results}:{search_query}",
                download=False
            )

            if search_results and 'entries' in search_results:
                for entry in search_results['entries']:
                    if entry:
                        results.append({
                            'url': f"https://www.youtube.com/watch?v={entry['id']}",
                            'title': entry.get('title', 'Unknown'),
                            'upload_date': entry.get('upload_date', '')
                        })

    except Exception as e:
        logger.error(f"Search failed for '{search_query}': {e}")

    return results


def find_video_for_date(
    date_str: str,
    year: int = 2024,
    channel: str = "Prea Mult Banciu"
) -> Optional[Dict[str, str]]:
    """
    Find a Banciu video for a specific date.

    Tries multiple search variations:
    1. "Prea Mult Banciu - <date>"
    2. "PreaMultBanciu - <date>"

    Args:
        date_str: Romanian date string like "5 Decembrie"
        year: Year (default: 2024)
        channel: Channel name for searching

    Returns:
        Dict with 'url', 'title', 'date' or None if not found
    """
    logger.info(f"Searching for video: {date_str}")

    # Parse date to standard format
    standard_date = parse_romanian_date(date_str, year)
    if not standard_date:
        logger.error(f"Could not parse date: {date_str}")
        return None

    # Try different search patterns
    search_patterns = [
        f"Prea Mult Banciu - {date_str}",
        f"PreaMultBanciu - {date_str}",
        f"Prea Mult Banciu {date_str}",
        f"PreaMultBanciu {date_str}",
    ]

    for pattern in search_patterns:
        logger.debug(f"Trying search pattern: {pattern}")
        results = search_youtube_for_video(pattern, max_results=3)

        for result in results:
            title = result['title']

            # Check if title matches expected format
            # Should contain the date string
            if date_str.lower() in title.lower():
                logger.info(f"Found video: {title}")
                return {
                    'url': result['url'],
                    'title': title,
                    'date': standard_date
                }

    logger.warning(f"No video found for: {date_str}")
    return None


def fetch_videos_for_dates(
    dates: List[str],
    year: int = 2024
) -> List[Dict[str, str]]:
    """
    Fetch videos for a list of dates.

    Args:
        dates: List of Romanian date strings
        year: Year for the dates

    Returns:
        List of video dicts with 'url', 'title', 'date'
    """
    videos = []

    for date_str in dates:
        video = find_video_for_date(date_str, year)
        if video:
            videos.append(video)
        else:
            logger.warning(f"Skipping {date_str} - not found")

    return videos


def save_videos_to_csv(videos: List[Dict[str, str]], output_file: str) -> None:
    """
    Save video list to CSV file.

    Args:
        videos: List of video dicts
        output_file: Path to output CSV file
    """
    output_path = Path(output_file)

    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['url', 'title', 'date'])
        writer.writeheader()
        writer.writerows(videos)

    logger.info(f"Saved {len(videos)} videos to {output_file}")


def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(
        description='Fetch Radu Banciu YouTube videos by date'
    )
    parser.add_argument(
        '--output-file',
        default='banciu_videos.csv',
        help='Output CSV file path (default: banciu_videos.csv)'
    )
    parser.add_argument(
        '--year',
        type=int,
        default=2024,
        help='Year for the dates (default: 2024)'
    )
    parser.add_argument(
        '--dates',
        nargs='+',
        help='Romanian dates to search for (e.g., "5 Decembrie" "27 Noiembrie")'
    )
    parser.add_argument(
        '--use-default-dates',
        action='store_true',
        help='Use the predefined list of dates'
    )

    args = parser.parse_args()

    # Default dates from user request
    default_dates = [
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
        "11 Octombrie",  # Fixed typo: "Ocrombrie" -> "Octombrie"
        "9 Octombrie",
        "17 Septembrie",
    ]

    # Determine which dates to use
    if args.use_default_dates or not args.dates:
        dates = default_dates
        logger.info("Using default date list")
    else:
        dates = args.dates

    logger.info(f"Fetching videos for {len(dates)} dates")

    # Fetch videos
    videos = fetch_videos_for_dates(dates, args.year)

    if not videos:
        logger.error("No videos found!")
        sys.exit(1)

    # Save to CSV
    save_videos_to_csv(videos, args.output_file)

    # Summary
    logger.info("=" * 60)
    logger.info(f"Successfully found {len(videos)} out of {len(dates)} videos")
    logger.info(f"Output saved to: {args.output_file}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
