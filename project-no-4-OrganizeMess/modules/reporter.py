"""
reporter.py
-----------
Generates the final report bundle: cleanup_report.csv/.xlsx/.json/.txt and
execution_log.txt, summarizing the entire run (scan stats, duplicates,
plan, and execution results).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import pandas as pd

from modules.duplicate_detector import DuplicateGroup
from modules.organizer import ExecutionResult
from modules.planner import ExecutionPlan
from modules.scanner import ScanResult
from modules.utils import (
    LOGS_DIR,
    REPORTS_DIR,
    format_timestamp,
    human_readable_size,
    setup_logger,
)

logger = setup_logger()


def _build_summary_dict(
    scan_result: ScanResult,
    duplicate_groups: list[DuplicateGroup],
    plan: ExecutionPlan,
    execution_result: Optional[ExecutionResult],
) -> dict:
    """Assemble the master summary dictionary shared by all report formats."""
    total_wasted = sum(g.wasted_bytes for g in duplicate_groups)

    summary = {
        "generated_at": format_timestamp(),
        "scan_summary": {
            "total_files": scan_result.total_files,
            "total_folders": scan_result.total_folders,
            "total_size_bytes": scan_result.total_size_bytes,
            "total_size_human": human_readable_size(scan_result.total_size_bytes),
            "category_breakdown": scan_result.category_breakdown,
            "type_breakdown": scan_result.type_breakdown,
            "empty_files_count": len(scan_result.empty_files),
            "old_files_count": len(scan_result.old_files),
            "recent_files_count": len(scan_result.recent_files),
        },
        "duplicate_summary": {
            "duplicate_groups_found": len(duplicate_groups),
            "redundant_file_count": sum(len(g.redundant) for g in duplicate_groups),
            "space_reclaimable_bytes": total_wasted,
            "space_reclaimable_human": human_readable_size(total_wasted),
        },
        "plan_summary": {
            "total_operations": plan.total_operations,
            "moves": len(plan.moves),
            "renames": len(plan.renames),
            "duplicate_flags": len(plan.duplicate_flags),
            "large_file_flags": len(plan.large_file_flags),
            "old_file_flags": len(plan.old_file_flags),
            "empty_file_flags": len(plan.empty_file_flags),
            "recommended_deletes": len(plan.recommended_deletes),
        },
    }

    if execution_result is not None:
        summary["execution_summary"] = {
            "files_copied": execution_result.files_copied,
            "files_renamed_on_copy": execution_result.files_renamed_on_copy,
            "recommended_deletes_copied": execution_result.recommended_deletes_copied,
            "bytes_copied": execution_result.bytes_copied,
            "bytes_copied_human": human_readable_size(execution_result.bytes_copied),
            "category_counts": execution_result.category_counts,
            "error_count": len(execution_result.errors),
            "errors": execution_result.errors,
        }

    return summary


def generate_reports(
    scan_result: ScanResult,
    duplicate_groups: list[DuplicateGroup],
    plan: ExecutionPlan,
    execution_result: Optional[ExecutionResult] = None,
    reports_dir: Optional[Path] = None,
) -> dict[str, Path]:
    """Write cleanup_report.csv/.xlsx/.json/.txt into the reports directory.

    Args:
        scan_result: Output of scanner.scan_folder().
        duplicate_groups: Output of duplicate_detector.find_content_duplicates().
        plan: Output of planner.build_plan().
        execution_result: Output of organizer.execute_plan(), if execution
            has already happened. Omit if only the dry-run has occurred.
        reports_dir: Destination folder. Defaults to REPORTS_DIR.

    Returns:
        Dict mapping report format ("csv", "xlsx", "json", "txt") to the
        Path of the generated file.
    """
    out_dir = reports_dir or REPORTS_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = _build_summary_dict(scan_result, duplicate_groups, plan, execution_result)
    file_df = scan_result.to_dataframe()

    paths: dict[str, Path] = {}

    # --- CSV: flat file-level detail table ---
    csv_path = out_dir / "cleanup_report.csv"
    file_df.to_csv(csv_path, index=False)
    paths["csv"] = csv_path

    # --- XLSX: multi-sheet workbook (files + summary) ---
    xlsx_path = out_dir / "cleanup_report.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        file_df.to_excel(writer, sheet_name="Files", index=False)

        summary_rows = []
        for section, values in summary.items():
            if isinstance(values, dict):
                for k, v in values.items():
                    if isinstance(v, dict):
                        for kk, vv in v.items():
                            summary_rows.append({"section": section, "metric": f"{k}.{kk}", "value": vv})
                    elif isinstance(v, list):
                        summary_rows.append({"section": section, "metric": k, "value": "; ".join(map(str, v)) or "none"})
                    else:
                        summary_rows.append({"section": section, "metric": k, "value": v})
            else:
                summary_rows.append({"section": section, "metric": "-", "value": values})
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        dup_rows = [
            {
                "hash": g.file_hash[:12],
                "kept_original": g.original.name,
                "redundant_file": r.name,
                "redundant_path": str(r.path),
                "size_bytes": r.size_bytes,
            }
            for g in duplicate_groups
            for r in g.redundant
        ]
        pd.DataFrame(dup_rows).to_excel(writer, sheet_name="Duplicates", index=False)
    paths["xlsx"] = xlsx_path

    # --- JSON: full structured summary ---
    json_path = out_dir / "cleanup_report.json"
    json_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
    paths["json"] = json_path

    # --- TXT: human-readable plain text summary ---
    txt_path = out_dir / "cleanup_report.txt"
    lines = [
        "ORGANIZE MESS - CLEANUP REPORT",
        "=" * 40,
        f"Generated: {summary['generated_at']}",
        "",
        "SCAN SUMMARY",
        "-" * 40,
    ]
    for k, v in summary["scan_summary"].items():
        lines.append(f"{k}: {v}")
    lines += ["", "DUPLICATE SUMMARY", "-" * 40]
    for k, v in summary["duplicate_summary"].items():
        lines.append(f"{k}: {v}")
    lines += ["", "PLAN SUMMARY", "-" * 40]
    for k, v in summary["plan_summary"].items():
        lines.append(f"{k}: {v}")
    if "execution_summary" in summary:
        lines += ["", "EXECUTION SUMMARY", "-" * 40]
        for k, v in summary["execution_summary"].items():
            lines.append(f"{k}: {v}")
    txt_path.write_text("\n".join(lines), encoding="utf-8")
    paths["txt"] = txt_path

    logger.info(f"Reports generated in {out_dir}: {list(paths.keys())}")

    return paths
