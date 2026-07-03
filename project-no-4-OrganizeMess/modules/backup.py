"""
backup.py
---------
Handles the mandatory safety backup step: copies the entire source folder
verbatim to a backup location before any scanning, planning, or execution
happens. This is the foundation of the app's "never touch originals" safety
guarantee.
"""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from modules.utils import BACKUP_DIR, SOURCE_DIR, human_readable_size, setup_logger

logger = setup_logger()


def create_backup(source_dir: Optional[Path] = None, backup_dir: Optional[Path] = None) -> dict:
    """Copy source_dir verbatim into backup_dir, preserving structure and timestamps.

    The backup directory is wiped and fully recreated on each call so the
    backup always reflects the current state of the source folder at the
    moment scanning begins.

    Args:
        source_dir: Folder to back up. Defaults to SOURCE_DIR.
        backup_dir: Destination for the backup. Defaults to BACKUP_DIR.

    Returns:
        Summary dict with file_count, total_size_bytes, total_size_human,
        source, destination, and completed_at timestamp.
    """
    source = source_dir or SOURCE_DIR
    dest = backup_dir or BACKUP_DIR

    if not source.exists():
        raise FileNotFoundError(
            f"Source folder does not exist: {source}. Generate the dummy data first."
        )

    if dest.exists():
        shutil.rmtree(dest)

    # copytree with copy2 preserves metadata (mtime, permissions) where the OS allows.
    shutil.copytree(source, dest, copy_function=shutil.copy2)

    file_count = 0
    total_size = 0
    for path in dest.rglob("*"):
        if path.is_file():
            file_count += 1
            total_size += path.stat().st_size

    summary = {
        "file_count": file_count,
        "total_size_bytes": total_size,
        "total_size_human": human_readable_size(total_size),
        "source": str(source),
        "destination": str(dest),
        "completed_at": datetime.now().isoformat(),
    }

    logger.info(
        f"Backup complete: {file_count} files ({summary['total_size_human']}) "
        f"copied from {source} to {dest}"
    )

    return summary


def verify_backup(source_dir: Optional[Path] = None, backup_dir: Optional[Path] = None) -> bool:
    """Sanity-check that the backup has the same file count as the source.

    Args:
        source_dir: Original folder. Defaults to SOURCE_DIR.
        backup_dir: Backup folder. Defaults to BACKUP_DIR.

    Returns:
        True if file counts match between source and backup.
    """
    source = source_dir or SOURCE_DIR
    dest = backup_dir or BACKUP_DIR

    if not source.exists() or not dest.exists():
        return False

    source_count = sum(1 for p in source.rglob("*") if p.is_file())
    backup_count = sum(1 for p in dest.rglob("*") if p.is_file())

    return source_count == backup_count
