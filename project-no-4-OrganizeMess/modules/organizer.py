"""
organizer.py
------------
Executes the approved plan. Strictly copy-only: originals in data/Downloads
and data/Downloads_Backup are never modified, moved, or deleted. Organized
copies land in generated/Organized/<Category>/, and recommended-delete
items are copied (not removed) into
generated/Organized/_Recommended_For_Deletion/ for manual human review.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from modules.duplicate_detector import DuplicateGroup
from modules.scanner import ScanResult
from modules.utils import (
    ORGANIZED_DIR,
    RECOMMENDED_DELETE_DIRNAME,
    ensure_dirs,
    safe_destination_name,
    setup_logger,
)

logger = setup_logger()


@dataclass
class ExecutionResult:
    """Summary of what actually happened during execution."""

    files_copied: int = 0
    files_renamed_on_copy: int = 0
    recommended_deletes_copied: int = 0
    bytes_copied: int = 0
    errors: list[str] = field(default_factory=list)
    category_counts: dict[str, int] = field(default_factory=dict)


def execute_plan(
    scan_result: ScanResult,
    duplicate_groups: list[DuplicateGroup],
    organized_dir: Path | None = None,
) -> ExecutionResult:
    """Copy every scanned file into its categorized destination folder.

    Originals are never touched. Duplicate files flagged as "redundant"
    (i.e. everything in a duplicate group except the earliest-modified
    original) are copied into a separate _Recommended_For_Deletion folder
    instead of their normal category folder, so the user can review and
    delete them manually if desired.

    Args:
        scan_result: Output of scanner.scan_folder().
        duplicate_groups: Output of duplicate_detector.find_content_duplicates().
        organized_dir: Root destination folder. Defaults to ORGANIZED_DIR.

    Returns:
        An ExecutionResult summarizing what was copied.
    """
    dest_root = organized_dir or ORGANIZED_DIR
    ensure_dirs(dest_root)

    # Build the set of "redundant" (should go to recommended-delete) paths.
    redundant_paths: set[Path] = set()
    for group in duplicate_groups:
        for record in group.redundant:
            redundant_paths.add(record.path)

    result = ExecutionResult()

    for record in scan_result.files:
        try:
            if record.path in redundant_paths:
                target_dir = dest_root / RECOMMENDED_DELETE_DIRNAME
            else:
                target_dir = dest_root / record.category

            dest_path = safe_destination_name(target_dir, record.name)
            if dest_path.name != record.name:
                result.files_renamed_on_copy += 1

            shutil.copy2(record.path, dest_path)

            result.files_copied += 1
            result.bytes_copied += record.size_bytes

            if record.path in redundant_paths:
                result.recommended_deletes_copied += 1
            else:
                result.category_counts[record.category] = (
                    result.category_counts.get(record.category, 0) + 1
                )

        except (OSError, PermissionError, shutil.Error) as exc:
            error_msg = f"Failed to copy {record.path}: {exc}"
            logger.error(error_msg)
            result.errors.append(error_msg)

    logger.info(
        f"Execution complete: {result.files_copied} files copied "
        f"({result.recommended_deletes_copied} to recommended-delete folder), "
        f"{result.files_renamed_on_copy} renamed for collision safety, "
        f"{len(result.errors)} errors"
    )

    return result
