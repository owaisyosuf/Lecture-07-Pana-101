"""
utils.py
--------
Shared configuration, constants, and helper functions used across the
Organize Mess application.

To reuse this app on a different source folder later, change SOURCE_DIR
below to point at the folder you actually want to organize, then run the
app again. Nothing else in the codebase needs to change.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Final

# --------------------------------------------------------------------------
# Reusability configuration
# --------------------------------------------------------------------------
# This is the ONLY line you need to edit to point the tool at a different
# folder in the future. Everything else (backup path, organized output,
# reports) is derived automatically relative to the project root.
BASE_DIR: Final[Path] = Path(__file__).resolve().parent.parent
SOURCE_DIR: Final[Path] = BASE_DIR / "data" / "Downloads"
BACKUP_DIR: Final[Path] = BASE_DIR / "data" / "Downloads_Backup"
ORGANIZED_DIR: Final[Path] = BASE_DIR / "generated" / "Organized"
REPORTS_DIR: Final[Path] = BASE_DIR / "generated" / "Reports"
LOGS_DIR: Final[Path] = BASE_DIR / "generated" / "Logs"
RECOMMENDED_DELETE_DIRNAME: Final[str] = "_Recommended_For_Deletion"

# --------------------------------------------------------------------------
# Category mapping
# --------------------------------------------------------------------------
CATEGORY_MAP: Final[dict[str, list[str]]] = {
    "Images": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".svg", ".webp", ".heic", ".tiff"],
    "Documents": [".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls", ".xlsx",
                  ".ppt", ".pptx", ".csv"],
    "Videos": [".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm"],
    "Audio": [".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"],
    "Archives": [".zip", ".rar", ".7z", ".tar", ".gz"],
    "Programming": [".py", ".js", ".html", ".css", ".java", ".cpp", ".c", ".json",
                     ".ipynb", ".sql", ".sh"],
    "Data": [".json", ".csv", ".xml", ".yaml", ".yml", ".parquet"],
    "Others": [],
}

# Explicit extension -> category lookup (JSON/CSV appear in two candidate
# groups above; we resolve the ambiguity once, here, in a single source of
# truth so scanner/planner/organizer never disagree with each other).
EXTENSION_TO_CATEGORY: Final[dict[str, str]] = {}
for _category, _extensions in CATEGORY_MAP.items():
    for _ext in _extensions:
        EXTENSION_TO_CATEGORY.setdefault(_ext, _category)
# Manual overrides for extensions that are genuinely ambiguous.
EXTENSION_TO_CATEGORY[".json"] = "Data"
EXTENSION_TO_CATEGORY[".csv"] = "Data"
EXTENSION_TO_CATEGORY[".xml"] = "Data"

OLD_FILE_THRESHOLD_DAYS: Final[int] = 180
LARGE_FILE_THRESHOLD_BYTES: Final[int] = 5 * 1024 * 1024  # 5 MB (kept small so the demo project stays lightweight)
RECENT_FILE_THRESHOLD_DAYS: Final[int] = 7


def get_category(extension: str) -> str:
    """Return the organizational category for a given file extension.

    Args:
        extension: File extension including the leading dot, e.g. ".pdf".

    Returns:
        Category name such as "Images" or "Others" if unrecognized.
    """
    return EXTENSION_TO_CATEGORY.get(extension.lower(), "Others")


def setup_logger(name: str = "organize_mess") -> logging.Logger:
    """Configure and return a logger that writes to generated/Logs/.

    Args:
        name: Logger name.

    Returns:
        A configured Logger instance with both file and stream handlers.
    """
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)

    if logger.handlers:
        # Avoid duplicate handlers when Streamlit re-runs the script.
        return logger

    logger.setLevel(logging.INFO)

    log_file = LOGS_DIR / "execution_log.txt"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


def compute_file_hash(file_path: Path, chunk_size: int = 65536) -> str:
    """Compute the SHA-256 hash of a file's contents.

    Args:
        file_path: Path to the file to hash.
        chunk_size: Number of bytes to read per chunk (memory efficiency).

    Returns:
        Hex digest string of the file's SHA-256 hash. Returns an empty
        string if the file cannot be read.
    """
    sha256 = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError):
        return ""


def human_readable_size(num_bytes: float) -> str:
    """Convert a byte count into a human-readable string.

    Args:
        num_bytes: Size in bytes.

    Returns:
        Formatted string such as "12.3 MB".
    """
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(num_bytes) < 1024.0:
            return f"{num_bytes:3.1f} {unit}"
        num_bytes /= 1024.0
    return f"{num_bytes:.1f} PB"


def safe_destination_name(destination_folder: Path, filename: str) -> Path:
    """Generate a collision-safe destination path.

    If `destination_folder / filename` already exists, appends
    " (1)", " (2)", etc. before the extension until a free name is found.

    Args:
        destination_folder: Target directory (may not exist yet).
        filename: Original file name including extension.

    Returns:
        A Path inside destination_folder guaranteed not to already exist
        at the time of the call.
    """
    destination_folder.mkdir(parents=True, exist_ok=True)
    candidate = destination_folder / filename
    if not candidate.exists():
        return candidate

    stem = Path(filename).stem
    suffix = Path(filename).suffix
    counter = 1
    while True:
        candidate = destination_folder / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def days_since_modified(file_path: Path) -> int:
    """Return the number of days since a file was last modified.

    Args:
        file_path: Path to inspect.

    Returns:
        Integer number of days since last modification.
    """
    mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
    return (datetime.now() - mtime).days


def ensure_dirs(*dirs: Path) -> None:
    """Create each given directory (and parents) if it does not exist."""
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def format_timestamp() -> str:
    """Return the current timestamp formatted for filenames/reports."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
