"""
scanner.py
----------
Scans the source folder and produces a rich set of statistics: file/folder
counts, type breakdowns, largest/smallest files, empty files, old files,
recently modified files, and raw file metadata used by later stages
(duplicate detection, planning).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from modules.utils import (
    OLD_FILE_THRESHOLD_DAYS,
    RECENT_FILE_THRESHOLD_DAYS,
    LARGE_FILE_THRESHOLD_BYTES,
    SOURCE_DIR,
    days_since_modified,
    get_category,
    human_readable_size,
    setup_logger,
)

logger = setup_logger()


@dataclass
class FileRecord:
    """Metadata captured for a single scanned file."""

    path: Path
    name: str
    extension: str
    category: str
    size_bytes: int
    modified_days_ago: int
    is_empty: bool
    is_large: bool
    is_old: bool
    is_recent: bool


@dataclass
class ScanResult:
    """Aggregated results of a folder scan."""

    total_files: int = 0
    total_folders: int = 0
    total_size_bytes: int = 0
    files: list[FileRecord] = field(default_factory=list)
    type_breakdown: dict[str, int] = field(default_factory=dict)
    category_breakdown: dict[str, int] = field(default_factory=dict)
    empty_files: list[FileRecord] = field(default_factory=list)
    old_files: list[FileRecord] = field(default_factory=list)
    recent_files: list[FileRecord] = field(default_factory=list)
    largest_files: list[FileRecord] = field(default_factory=list)
    smallest_files: list[FileRecord] = field(default_factory=list)

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the scanned file list into a pandas DataFrame."""
        if not self.files:
            return pd.DataFrame(columns=[
                "name", "path", "extension", "category", "size_bytes",
                "size_human", "modified_days_ago", "is_empty", "is_large",
                "is_old", "is_recent",
            ])
        rows = [
            {
                "name": f.name,
                "path": str(f.path),
                "extension": f.extension,
                "category": f.category,
                "size_bytes": f.size_bytes,
                "size_human": human_readable_size(f.size_bytes),
                "modified_days_ago": f.modified_days_ago,
                "is_empty": f.is_empty,
                "is_large": f.is_large,
                "is_old": f.is_old,
                "is_recent": f.is_recent,
            }
            for f in self.files
        ]
        return pd.DataFrame(rows)


def scan_folder(source_dir: Optional[Path] = None) -> ScanResult:
    """Walk the source folder and collect statistics on every file found.

    Args:
        source_dir: Folder to scan. Defaults to SOURCE_DIR.

    Returns:
        A populated ScanResult.
    """
    root = source_dir or SOURCE_DIR
    if not root.exists():
        raise FileNotFoundError(f"Folder to scan does not exist: {root}")

    result = ScanResult()

    for path in root.rglob("*"):
        if path.is_dir():
            result.total_folders += 1
            continue
        if not path.is_file():
            continue

        try:
            size = path.stat().st_size
        except OSError:
            continue

        ext = path.suffix.lower()
        category = get_category(ext)
        days_ago = days_since_modified(path)

        record = FileRecord(
            path=path,
            name=path.name,
            extension=ext or "(none)",
            category=category,
            size_bytes=size,
            modified_days_ago=days_ago,
            is_empty=(size == 0),
            is_large=(size >= LARGE_FILE_THRESHOLD_BYTES),
            is_old=(days_ago >= OLD_FILE_THRESHOLD_DAYS),
            is_recent=(days_ago <= RECENT_FILE_THRESHOLD_DAYS),
        )

        result.files.append(record)
        result.total_files += 1
        result.total_size_bytes += size

        result.type_breakdown[record.extension] = result.type_breakdown.get(record.extension, 0) + 1
        result.category_breakdown[category] = result.category_breakdown.get(category, 0) + 1

        if record.is_empty:
            result.empty_files.append(record)
        if record.is_old:
            result.old_files.append(record)
        if record.is_recent:
            result.recent_files.append(record)

    sorted_by_size = sorted(result.files, key=lambda f: f.size_bytes, reverse=True)
    result.largest_files = sorted_by_size[:10]
    result.smallest_files = sorted(
        [f for f in result.files if not f.is_empty], key=lambda f: f.size_bytes
    )[:10]

    logger.info(
        f"Scan complete: {result.total_files} files, {result.total_folders} folders, "
        f"{human_readable_size(result.total_size_bytes)} total"
    )

    return result


def find_duplicate_names(scan_result: ScanResult) -> dict[str, list[FileRecord]]:
    """Group files that share the exact same filename across folders.

    Args:
        scan_result: Output of scan_folder().

    Returns:
        Dict mapping filename -> list of FileRecords with that name
        (only names that appear more than once).
    """
    by_name: dict[str, list[FileRecord]] = {}
    for f in scan_result.files:
        by_name.setdefault(f.name, []).append(f)
    return {name: records for name, records in by_name.items() if len(records) > 1}
