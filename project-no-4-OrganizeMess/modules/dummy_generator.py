"""
dummy_generator.py
-------------------
Generates a realistic, messy, synthetic "Downloads" folder for demo
purposes. This never touches a real user folder — everything is created
from scratch under data/Downloads/.
"""

from __future__ import annotations

import json
import random
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from modules.utils import SOURCE_DIR, setup_logger

logger = setup_logger()

# --------------------------------------------------------------------------
# Content generators (writes bytes that "look like" the given file type,
# without needing real PDF/Office libraries for the dummy layer).
# --------------------------------------------------------------------------

_LOREM_WORDS = (
    "invoice project resume budget notes summary draft final report "
    "screenshot holiday vacation family meeting client presentation "
    "backup archive photo video music design mockup layout ticket "
    "receipt statement contract agreement proposal timeline schedule"
).split()


def _random_text(min_words: int = 20, max_words: int = 120) -> str:
    n = random.randint(min_words, max_words)
    return " ".join(random.choice(_LOREM_WORDS) for _ in range(n))


def _write_text_like_file(path: Path, size_hint: str = "normal") -> None:
    """Write a plain-text-ish payload; used for pdf/doc/ppt/txt stand-ins."""
    if size_hint == "empty":
        path.write_bytes(b"")
        return
    if size_hint == "large":
        # 6-14 MB of repeated text to simulate a "large file" (safely above
        # the 5 MB threshold) without bloating the demo project's disk footprint.
        chunk = (_random_text(200, 200) + "\n").encode("utf-8")
        target_bytes = random.randint(6, 14) * 1024 * 1024
        with open(path, "wb") as f:
            written = 0
            while written < target_bytes:
                f.write(chunk)
                written += len(chunk)
        return
    path.write_text(_random_text(), encoding="utf-8")


def _write_csv(path: Path) -> None:
    rows = ["id,name,amount,date"]
    for i in range(random.randint(5, 40)):
        rows.append(f"{i},{random.choice(_LOREM_WORDS)},{random.randint(10, 9999)},2025-0{random.randint(1,9)}-1{random.randint(0,9)}")
    path.write_text("\n".join(rows), encoding="utf-8")


def _write_json(path: Path) -> None:
    data = {
        "name": random.choice(_LOREM_WORDS),
        "id": random.randint(1000, 9999),
        "tags": random.sample(_LOREM_WORDS, k=4),
        "active": random.choice([True, False]),
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _write_html(path: Path) -> None:
    title = random.choice(_LOREM_WORDS).title()
    path.write_text(
        f"<html><head><title>{title}</title></head>"
        f"<body><h1>{title}</h1><p>{_random_text(10, 30)}</p></body></html>",
        encoding="utf-8",
    )


def _write_py(path: Path) -> None:
    fname = random.choice(["process", "helper", "main", "utils", "script"])
    path.write_text(
        f"def {fname}():\n"
        f'    """Auto-generated dummy script."""\n'
        f"    data = {random.sample(range(100), 5)}\n"
        f"    return sum(data)\n\n\n"
        f"if __name__ == '__main__':\n"
        f"    print({fname}())\n",
        encoding="utf-8",
    )


def _write_image_placeholder(path: Path) -> None:
    """Write a tiny valid 1x1 PNG (real magic bytes) so it 'is' an image."""
    png_bytes = bytes.fromhex(
        "89504e470d0a1a0a0000000d4948445200000001000000010802000000907753"
        "de0000000c4944415408d763f8cfc0c0c000000004000178cd12ce0000000049454e44ae426082"
    )
    path.write_bytes(png_bytes)


def _write_zip(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as zf:
        for _ in range(random.randint(1, 4)):
            zf.writestr(f"{random.choice(_LOREM_WORDS)}.txt", _random_text(10, 40))


def _set_random_mtime(path: Path, max_days_back: int = 400) -> None:
    """Backdate a file's modified time to simulate old/recent files."""
    days_back = random.randint(0, max_days_back)
    new_time = datetime.now() - timedelta(days=days_back)
    ts = new_time.timestamp()
    import os
    os.utime(path, (ts, ts))


_EXT_WRITERS = {
    ".pdf": _write_text_like_file,
    ".doc": _write_text_like_file,
    ".docx": _write_text_like_file,
    ".xlsx": _write_csv,
    ".pptx": _write_text_like_file,
    ".txt": _write_text_like_file,
    ".csv": _write_csv,
    ".json": _write_json,
    ".html": _write_html,
    ".py": _write_py,
    ".zip": _write_zip,
    ".jpg": _write_image_placeholder,
    ".png": _write_image_placeholder,
    ".mp4": _write_text_like_file,
    ".mp3": _write_text_like_file,
}


def _write_file(path: Path, ext: str, size_hint: str = "normal") -> None:
    writer = _EXT_WRITERS.get(ext, _write_text_like_file)
    if writer in (_write_text_like_file,):
        writer(path, size_hint)
    else:
        writer(path)
        if size_hint == "empty":
            path.write_bytes(b"")


# --------------------------------------------------------------------------
# Main generation routine
# --------------------------------------------------------------------------

def generate_dummy_downloads(target_dir: Optional[Path] = None, seed: Optional[int] = 42) -> dict:
    """Populate a synthetic, messy Downloads folder with ~100-150 files.

    Wipes and recreates target_dir every time it's called so re-runs are
    deterministic and reproducible.

    Args:
        target_dir: Folder to populate. Defaults to SOURCE_DIR (data/Downloads).
        seed: Random seed for reproducibility. Pass None for true randomness.

    Returns:
        Summary dict with counts of files/folders created.
    """
    if seed is not None:
        random.seed(seed)

    root = target_dir or SOURCE_DIR

    # Clean slate.
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    subfolders = [
        root,
        root / "Old Stuff",
        root / "Old Stuff" / "2023 backup",
        root / "Work Files",
        root / "Screenshots",
        root / "Random",
    ]
    for folder in subfolders:
        folder.mkdir(parents=True, exist_ok=True)

    file_count = 0
    duplicate_content_pool: list[tuple[Path, str]] = []  # (path, ext) for content-dup reuse

    base_names = [
        "Resume_Final", "Invoice", "Project_Report", "Budget_2025", "Holiday_Photo",
        "Meeting_Notes", "Presentation", "Client_Contract", "Vacation_Plan",
        "Design_Mockup", "Ticket_Receipt", "Timeline", "Backup_Data", "Draft_Proposal",
        "Family_Photo", "Old_Notes", "Music_Track", "Movie", "Screenshot",
        "Statement", "Agreement", "Summary", "Layout", "Schedule", "IMG",
    ]
    extensions = [".pdf", ".docx", ".xlsx", ".pptx", ".txt", ".csv", ".json",
                  ".html", ".py", ".zip", ".jpg", ".png", ".mp4", ".mp3"]

    target_total = random.randint(100, 150)

    # --- 1. Bulk of unique-ish files spread across folders ---
    while file_count < int(target_total * 0.7):
        name = random.choice(base_names)
        ext = random.choice(extensions)
        folder = random.choice(subfolders)
        suffix = ""
        if random.random() < 0.15:
            suffix = f" ({random.randint(1,9)})"
        elif random.random() < 0.1:
            suffix = "_copy"
        elif random.random() < 0.1:
            suffix = "_Final"

        fname = f"{name}{suffix}{ext}"
        fpath = folder / fname
        if fpath.exists():
            continue

        size_hint = "normal"
        roll = random.random()
        if roll < 0.05:
            size_hint = "empty"
        elif roll < 0.08:
            size_hint = "large"

        _write_file(fpath, ext, size_hint)
        _set_random_mtime(fpath)
        file_count += 1

        if size_hint == "normal" and random.random() < 0.3:
            duplicate_content_pool.append((fpath, ext))

    # --- 2. Exact duplicate FILES (same name AND same content, different folder) ---
    for _ in range(random.randint(6, 10)):
        if not duplicate_content_pool:
            break
        src, ext = random.choice(duplicate_content_pool)
        dest_folder = random.choice(subfolders)
        dest = dest_folder / src.name
        if dest.exists() or dest_folder == src.parent:
            continue
        dest.write_bytes(src.read_bytes())
        _set_random_mtime(dest)
        file_count += 1

    # --- 3. Same CONTENT, different filename (content-hash duplicates) ---
    for _ in range(random.randint(6, 10)):
        if not duplicate_content_pool:
            break
        src, ext = random.choice(duplicate_content_pool)
        new_name = f"{Path(src.name).stem}_copy{ext}"
        dest_folder = random.choice(subfolders)
        dest = dest_folder / new_name
        if dest.exists():
            continue
        dest.write_bytes(src.read_bytes())
        _set_random_mtime(dest)
        file_count += 1

    # --- 4. Same filename, DIFFERENT content, different folders (name-only dup) ---
    for _ in range(random.randint(5, 8)):
        name = random.choice(base_names)
        ext = random.choice(extensions)
        fname = f"{name}{ext}"
        chosen_folders = random.sample(subfolders, k=min(2, len(subfolders)))
        for folder in chosen_folders:
            fpath = folder / fname
            if fpath.exists():
                continue
            _write_file(fpath, ext, "normal")
            _set_random_mtime(fpath)
            file_count += 1

    # --- 5. A few guaranteed empty files ---
    for _ in range(random.randint(3, 6)):
        name = random.choice(base_names)
        ext = random.choice([".txt", ".pdf", ".docx", ".csv"])
        fpath = random.choice(subfolders) / f"{name}_empty{ext}"
        if fpath.exists():
            continue
        fpath.write_bytes(b"")
        _set_random_mtime(fpath)
        file_count += 1

    # --- 6. A couple guaranteed large files ---
    for _ in range(random.randint(2, 3)):
        fpath = random.choice(subfolders) / f"Movie_{random.randint(1,999)}.mp4"
        if fpath.exists():
            continue
        _write_file(fpath, ".mp4", "large")
        _set_random_mtime(fpath)
        file_count += 1

    total_folders = sum(1 for _ in root.rglob("*") if _.is_dir())
    logger.info(f"Generated dummy Downloads folder: {file_count} files, {total_folders} subfolders at {root}")

    return {
        "files_created": file_count,
        "folders_created": total_folders,
        "target_dir": str(root),
        "generated_at": datetime.now().isoformat(),
    }
