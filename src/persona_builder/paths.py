from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
INPUT_DIR = DATA_DIR / "input"
OUTPUT_DIR = DATA_DIR / "output"
TEMP_DIR = DATA_DIR / "temp"
SAMPLES_DIR = DATA_DIR / "samples"
WORLDVIEW_DIR = DATA_DIR / "worldview"

DEFAULT_VIDEO_LIST = INPUT_DIR / "banciu_videos.csv"
DEFAULT_SHOW_DATES = INPUT_DIR / "show_dates.txt"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR
DEFAULT_TEMP_DIR = TEMP_DIR
DEFAULT_SAMPLE_VIDEO_LIST = SAMPLES_DIR / "sample_videos.csv"
DEFAULT_WORLDVIEW_PATH = WORLDVIEW_DIR / "banciu_worldview.md"


def ensure_repo_layout() -> None:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    WORLDVIEW_DIR.mkdir(parents=True, exist_ok=True)

