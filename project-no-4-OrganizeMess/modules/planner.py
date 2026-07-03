"""
planner.py
----------
Builds the full dry-run execution plan: every MOVE, RENAME, FLAG, and
recommended DELETE operation the app would perform, without touching a
single file. This plan is what the user reviews and approves before
Step 7 (execute) is allowed to run.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from modules.duplicate_detector import DuplicateGroup, build_duplicate_lookup
from modules.scanner import FileRecord, ScanResult, find_duplicate_names
from modules.utils import (
    LARGE_FILE_THRESHOLD_BYTES,
    ORGANIZED_DIR,
    OLD_FILE_THRESHOLD_DAYS,
    human_readable_size,
    setup_logger,
)

logger = setup_logger()

OP_MOVE = "MOVE"
OP_RENAME = "RENAME"
OP_FLAG_DUPLICATE = "FLAG_DUPLICATE"
OP_FLAG_LARGE = "FLAG_LARGE"
OP_FLAG_OLD = "FLAG_OLD"
OP_FLAG_EMPTY = "FLAG_EMPTY"
OP_DELETE_RECOMMENDED = "DELETE_RECOMMENDED"


@dataclass
class PlanEntry:
    """A single line item in the execution plan."""

    operation: str
    source: str
    destination: str
    reason: str


@dataclass
class ExecutionPlan:
    """The complete dry-run plan, grouped by operation type."""

    moves: list[PlanEntry]
    renames: list[PlanEntry]
    duplicate_flags: list[PlanEntry]
    large_file_flags: list[PlanEntry]
    old_file_flags: list[PlanEntry]
    empty_file_flags: list[PlanEntry]
    recommended_deletes: list[PlanEntry]

    @property
    def total_operations(self) -> int:
        return (
            len(self.moves)
            + len(self.renames)
            + len(self.duplicate_flags)
            + len(self.large_file_flags)
            + len(self.old_file_flags)
            + len(self.empty_file_flags)
            + len(self.recommended_deletes)
        )

    @property
    def reclaimable_bytes(self) -> int:
        """Total bytes that would be freed if all recommended deletes were applied."""
        return sum(int(e.reason.split("bytes:")[-1]) for e in self.recommended_deletes if "bytes:" in e.reason)


def build_plan(
    scan_result: ScanResult,
    duplicate_groups: list[DuplicateGroup],
    organized_dir: Path | None = None,
) -> ExecutionPlan:
    """Construct the full dry-run plan from scan + duplicate detection results.

    Args:
        scan_result: Output of scanner.scan_folder().
        duplicate_groups: Output of duplicate_detector.find_content_duplicates().
        organized_dir: Root folder plan destinations are computed relative to.
            Defaults to ORGANIZED_DIR.

    Returns:
        A fully populated ExecutionPlan. No files are touched.
    """
    dest_root = organized_dir or ORGANIZED_DIR
    dup_lookup = build_duplicate_lookup(duplicate_groups)
    duplicate_name_groups = find_duplicate_names(scan_result)

    moves: list[PlanEntry] = []
    renames: list[PlanEntry] = []
    duplicate_flags: list[PlanEntry] = []
    large_flags: list[PlanEntry] = []
    old_flags: list[PlanEntry] = []
    empty_flags: list[PlanEntry] = []
    deletes: list[PlanEntry] = []

    # Track planned destination names per category folder to simulate
    # collision-safe renaming without touching disk.
    planned_names: dict[Path, set[str]] = {}

    for record in scan_result.files:
        category_dir = dest_root / record.category
        planned_names.setdefault(category_dir, set())

        target_name = record.name
        if target_name in planned_names[category_dir]:
            stem = Path(record.name).stem
            suffix = Path(record.name).suffix
            counter = 1
            while f"{stem} ({counter}){suffix}" in planned_names[category_dir]:
                counter += 1
            new_name = f"{stem} ({counter}){suffix}"
            renames.append(
                PlanEntry(
                    operation=OP_RENAME,
                    source=record.name,
                    destination=new_name,
                    reason="destination filename already exists in target category",
                )
            )
            target_name = new_name

        planned_names[category_dir].add(target_name)

        moves.append(
            PlanEntry(
                operation=OP_MOVE,
                source=str(record.path),
                destination=str(category_dir / target_name),
                reason=f"file type '{record.extension}' maps to category '{record.category}'",
            )
        )

        if record.is_large:
            large_flags.append(
                PlanEntry(
                    operation=OP_FLAG_LARGE,
                    source=str(record.path),
                    destination="-",
                    reason=f"{human_readable_size(record.size_bytes)} exceeds "
                            f"{human_readable_size(LARGE_FILE_THRESHOLD_BYTES)} threshold",
                )
            )

        if record.is_old:
            old_flags.append(
                PlanEntry(
                    operation=OP_FLAG_OLD,
                    source=str(record.path),
                    destination="-",
                    reason=f"last modified {record.modified_days_ago} days ago "
                            f"(older than {OLD_FILE_THRESHOLD_DAYS}-day threshold)",
                )
            )

        if record.is_empty:
            empty_flags.append(
                PlanEntry(
                    operation=OP_FLAG_EMPTY,
                    source=str(record.path),
                    destination="-",
                    reason="file has 0 bytes",
                )
            )

    # Content-duplicate flags + recommended deletes (never actually executed).
    for group in duplicate_groups:
        original = group.original
        for redundant in group.redundant:
            duplicate_flags.append(
                PlanEntry(
                    operation=OP_FLAG_DUPLICATE,
                    source=str(redundant.path),
                    destination="-",
                    reason=f"same SHA256 hash as '{original.name}'",
                )
            )
            deletes.append(
                PlanEntry(
                    operation=OP_DELETE_RECOMMENDED,
                    source=str(redundant.path),
                    destination="-",
                    reason=f"confirmed duplicate content; safe to remove manually after "
                            f"review | bytes:{redundant.size_bytes}",
                )
            )

    plan = ExecutionPlan(
        moves=moves,
        renames=renames,
        duplicate_flags=duplicate_flags,
        large_file_flags=large_flags,
        old_file_flags=old_flags,
        empty_file_flags=empty_flags,
        recommended_deletes=deletes,
    )

    logger.info(
        f"Plan built: {len(moves)} moves, {len(renames)} renames, "
        f"{len(duplicate_flags)} duplicate flags, {len(deletes)} recommended deletes "
        f"({human_readable_size(plan.reclaimable_bytes)} reclaimable)"
    )

    return plan
