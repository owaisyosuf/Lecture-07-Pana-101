"""
duplicate_detector.py
----------------------
Detects duplicate files by content (SHA-256 hash), independent of filename.
This catches both "same name AND same content" and "different name but
identical content" cases.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from modules.scanner import FileRecord, ScanResult
from modules.utils import compute_file_hash, setup_logger

logger = setup_logger()


@dataclass
class DuplicateGroup:
    """A group of two or more files sharing identical content."""

    file_hash: str
    files: list[FileRecord] = field(default_factory=list)

    @property
    def original(self) -> FileRecord:
        """The file considered 'kept' — earliest modified (oldest) copy."""
        return min(self.files, key=lambda f: f.path.stat().st_mtime)

    @property
    def redundant(self) -> list[FileRecord]:
        """All copies other than the original — candidates for cleanup."""
        orig = self.original
        return [f for f in self.files if f.path != orig.path]

    @property
    def wasted_bytes(self) -> int:
        """Disk space that could be reclaimed by removing redundant copies."""
        return sum(f.size_bytes for f in self.redundant)


def find_content_duplicates(scan_result: ScanResult) -> list[DuplicateGroup]:
    """Hash every non-empty file and group files with identical content.

    Args:
        scan_result: Output of scanner.scan_folder().

    Returns:
        List of DuplicateGroup objects, one per set of 2+ identical files.
        Empty files are excluded (hashing an empty file is meaningless and
        would otherwise incorrectly group all empty files together).
    """
    hash_map: dict[str, list[FileRecord]] = {}

    for record in scan_result.files:
        if record.is_empty:
            continue
        file_hash = compute_file_hash(record.path)
        if not file_hash:
            continue
        hash_map.setdefault(file_hash, []).append(record)

    groups = [
        DuplicateGroup(file_hash=h, files=records)
        for h, records in hash_map.items()
        if len(records) > 1
    ]

    total_wasted = sum(g.wasted_bytes for g in groups)
    logger.info(
        f"Duplicate detection complete: {len(groups)} duplicate groups found, "
        f"{total_wasted} bytes potentially reclaimable"
    )

    return groups


def build_duplicate_lookup(groups: list[DuplicateGroup]) -> dict[Path, DuplicateGroup]:
    """Build a Path -> DuplicateGroup lookup for quick membership checks.

    Args:
        groups: Output of find_content_duplicates().

    Returns:
        Dict mapping each file's Path to the DuplicateGroup it belongs to.
    """
    lookup: dict[Path, DuplicateGroup] = {}
    for group in groups:
        for record in group.files:
            lookup[record.path] = group
    return lookup
