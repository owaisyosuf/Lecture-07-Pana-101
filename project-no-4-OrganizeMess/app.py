"""
app.py
------
Organize Mess — a safe, dry-run-first file organization dashboard.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

# Make sure `modules` is importable regardless of the working directory
# Streamlit was launched from.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules import backup, dummy_generator, duplicate_detector, organizer, planner, reporter, scanner
from modules.utils import (
    BACKUP_DIR,
    ORGANIZED_DIR,
    REPORTS_DIR,
    SOURCE_DIR,
    human_readable_size,
)

# --------------------------------------------------------------------------
# Page config + theme
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Organize Mess",
    page_icon="🗂️",
    layout="wide",
    initial_sidebar_state="expanded",
)


def load_css() -> None:
    css_path = Path(__file__).resolve().parent / "assets" / "style.css"
    if css_path.exists():
        st.markdown(f"<style>{css_path.read_text()}</style>", unsafe_allow_html=True)


load_css()

# --------------------------------------------------------------------------
# Session state initialization
# --------------------------------------------------------------------------
DEFAULTS = {
    "dummy_generated": False,
    "backup_summary": None,
    "scan_result": None,
    "duplicate_groups": None,
    "plan": None,
    "plan_approved": False,
    "execution_result": None,
    "report_paths": None,
}
for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value


def badge(label: str, kind: str) -> str:
    return f'<span class="badge badge-{kind}">{label}</span>'


# --------------------------------------------------------------------------
# Sidebar navigation
# --------------------------------------------------------------------------
st.sidebar.title("🗂️ Organize Mess")
st.sidebar.caption("Safe, dry-run-first file organization")

page = st.sidebar.radio(
    "Navigate",
    [
        "🏠 Dashboard",
        "🔍 Folder Scanner",
        "📋 Cleaning Brief",
        "🧪 Dry Run",
        "✅ Execution",
        "📊 Reports",
        "ℹ️ About Project",
    ],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.markdown("**Pipeline status**")
pipeline_steps = [
    ("Dummy data generated", st.session_state.dummy_generated),
    ("Backup created", st.session_state.backup_summary is not None),
    ("Folder scanned", st.session_state.scan_result is not None),
    ("Plan built", st.session_state.plan is not None),
    ("Plan approved", st.session_state.plan_approved),
    ("Executed", st.session_state.execution_result is not None),
]
for label, done in pipeline_steps:
    icon = "✅" if done else "⬜"
    st.sidebar.markdown(f"{icon} {label}")


# ==========================================================================
# PAGE: Dashboard
# ==========================================================================
if page == "🏠 Dashboard":
    st.title("Organize Mess")
    st.caption("A safe file organization assistant — backup, analyze, plan, approve, then act.")

    st.markdown(
        '<div class="callout">This app never modifies or deletes your original files. '
        "Everything is copied. Nothing is deleted automatically — deletion is always left "
        "to you, after review.</div>",
        unsafe_allow_html=True,
    )

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Source files", st.session_state.scan_result.total_files if st.session_state.scan_result else "—")
    with col2:
        dup_count = len(st.session_state.duplicate_groups) if st.session_state.duplicate_groups else "—"
        st.metric("Duplicate groups", dup_count)
    with col3:
        ops = st.session_state.plan.total_operations if st.session_state.plan else "—"
        st.metric("Plan operations", ops)
    with col4:
        copied = st.session_state.execution_result.files_copied if st.session_state.execution_result else "—"
        st.metric("Files organized", copied)

    st.divider()

    st.subheader("Step 1 — Generate the mess")
    st.write(
        "This creates a synthetic, disposable `data/Downloads/` folder with ~100-150 "
        "realistic dummy files (documents, images, videos, duplicates, empty files, "
        "large files, nested folders). Your real Downloads folder is never touched."
    )
    gen_col1, gen_col2 = st.columns([1, 3])
    with gen_col1:
        if st.button("🎲 Generate dummy Downloads folder", use_container_width=True):
            with st.spinner("Generating realistic clutter..."):
                summary = dummy_generator.generate_dummy_downloads()
            st.session_state.dummy_generated = True
            # Reset downstream state since the source data changed.
            st.session_state.backup_summary = None
            st.session_state.scan_result = None
            st.session_state.duplicate_groups = None
            st.session_state.plan = None
            st.session_state.plan_approved = False
            st.session_state.execution_result = None
            st.session_state.report_paths = None
            st.success(f"Generated {summary['files_created']} files across {summary['folders_created']} folders.")

    if st.session_state.dummy_generated:
        st.markdown('<span class="badge badge-ok">Dummy data ready</span>', unsafe_allow_html=True)

    st.divider()

    st.subheader("Step 2 — Backup (mandatory safety step)")
    st.write(
        "Before anything is scanned or planned, the entire `data/Downloads/` folder is "
        "copied verbatim into `data/Downloads_Backup/`. This happens even though the "
        "source data is synthetic — it demonstrates the safety habit this project is "
        "built around, and costs nothing since there's nothing real to lose."
    )
    backup_col1, backup_col2 = st.columns([1, 3])
    with backup_col1:
        backup_disabled = not st.session_state.dummy_generated
        if st.button("🛡️ Run backup", use_container_width=True, disabled=backup_disabled):
            with st.spinner("Backing up data/Downloads to data/Downloads_Backup..."):
                summary = backup.create_backup()
            st.session_state.backup_summary = summary
            st.success(
                f"Backup complete: {summary['file_count']} files "
                f"({summary['total_size_human']}) copied."
            )
    if backup_disabled:
        st.caption("Generate the dummy Downloads folder first.")

    if st.session_state.backup_summary:
        b = st.session_state.backup_summary
        bc1, bc2, bc3 = st.columns(3)
        bc1.metric("Files backed up", b["file_count"])
        bc2.metric("Total size", b["total_size_human"])
        bc3.metric("Backup location", "Downloads_Backup/")
        st.markdown('<span class="badge badge-ok">Backup verified</span>', unsafe_allow_html=True)

    st.divider()
    st.info("Continue to **🔍 Folder Scanner** in the sidebar once the backup is complete.")


# ==========================================================================
# PAGE: Folder Scanner
# ==========================================================================
elif page == "🔍 Folder Scanner":
    st.title("🔍 Folder Scanner")
    st.caption("Analyze the (backed-up) source folder and surface statistics.")

    if st.session_state.backup_summary is None:
        st.warning("Complete the backup step on the Dashboard before scanning.")
        st.stop()

    if st.button("Run scan", type="primary"):
        with st.spinner("Scanning folder and hashing files for duplicates..."):
            scan_result = scanner.scan_folder()
            duplicate_groups = duplicate_detector.find_content_duplicates(scan_result)
        st.session_state.scan_result = scan_result
        st.session_state.duplicate_groups = duplicate_groups
        st.success("Scan complete.")

    sr = st.session_state.scan_result
    if sr is None:
        st.info("Click **Run scan** to analyze the folder.")
        st.stop()

    dup_groups = st.session_state.duplicate_groups or []
    dup_name_groups = scanner.find_duplicate_names(sr)

    st.subheader("Overview")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total files", sr.total_files)
    c2.metric("Total folders", sr.total_folders)
    c3.metric("Total size", human_readable_size(sr.total_size_bytes))
    c4.metric("Empty files", len(sr.empty_files))

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Old files (180d+)", len(sr.old_files))
    c6.metric("Recently modified (7d)", len(sr.recent_files))
    c7.metric("Duplicate name groups", len(dup_name_groups))
    c8.metric("Duplicate content groups", len(dup_groups))

    st.divider()

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### File types")
        type_df = pd.DataFrame(
            sorted(sr.type_breakdown.items(), key=lambda x: -x[1]), columns=["Extension", "Count"]
        )
        st.bar_chart(type_df.set_index("Extension"))

    with col_right:
        st.markdown("#### Categories")
        cat_df = pd.DataFrame(
            sorted(sr.category_breakdown.items(), key=lambda x: -x[1]), columns=["Category", "Count"]
        )
        st.bar_chart(cat_df.set_index("Category"))

    st.divider()

    with st.expander(f"📦 Largest files ({len(sr.largest_files)})"):
        largest_df = pd.DataFrame(
            [{"Name": f.name, "Size": human_readable_size(f.size_bytes), "Path": str(f.path)} for f in sr.largest_files]
        )
        st.dataframe(largest_df, use_container_width=True, hide_index=True)

    with st.expander(f"🪶 Smallest (non-empty) files ({len(sr.smallest_files)})"):
        smallest_df = pd.DataFrame(
            [{"Name": f.name, "Size": human_readable_size(f.size_bytes), "Path": str(f.path)} for f in sr.smallest_files]
        )
        st.dataframe(smallest_df, use_container_width=True, hide_index=True)

    with st.expander(f"🔁 Duplicate filenames across folders ({len(dup_name_groups)})"):
        if dup_name_groups:
            rows = []
            for name, records in dup_name_groups.items():
                for r in records:
                    rows.append({"Name": name, "Path": str(r.path), "Size": human_readable_size(r.size_bytes)})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.write("No duplicate filenames found.")

    with st.expander(f"🧬 Duplicate content (identical files) ({len(dup_groups)} groups)"):
        if dup_groups:
            rows = []
            for g in dup_groups:
                for r in g.files:
                    role = "Original (kept)" if r.path == g.original.path else "Redundant"
                    rows.append({
                        "Hash": g.file_hash[:12],
                        "Name": r.name,
                        "Role": role,
                        "Path": str(r.path),
                        "Size": human_readable_size(r.size_bytes),
                    })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.write("No content duplicates found.")

    with st.expander(f"🕳️ Empty files ({len(sr.empty_files)})"):
        if sr.empty_files:
            st.dataframe(
                pd.DataFrame([{"Name": f.name, "Path": str(f.path)} for f in sr.empty_files]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("No empty files found.")

    with st.expander("🔎 Search & filter all files"):
        search_term = st.text_input("Search by filename")
        category_filter = st.multiselect("Filter by category", options=sorted(sr.category_breakdown.keys()))
        df = sr.to_dataframe()
        if search_term:
            df = df[df["name"].str.contains(search_term, case=False, na=False)]
        if category_filter:
            df = df[df["category"].isin(category_filter)]
        st.dataframe(df, use_container_width=True, hide_index=True)


# ==========================================================================
# PAGE: Cleaning Brief
# ==========================================================================
elif page == "📋 Cleaning Brief":
    st.title("📋 Cleaning Brief")
    st.caption("Plain-English explanation of what 'clean' means for this project.")

    st.markdown(
        """
<div class="section-card">
<h4>What "clean" means here</h4>

- **Group files by type** — Images, Documents, Videos, Audio, Archives, Programming, Data, and Others each get their own folder.
- **Detect duplicate files** — files with identical content (by SHA-256 hash) are found regardless of filename.
- **Find duplicate names** — files sharing the same filename across different folders are surfaced separately from content duplicates.
- **Detect empty files** — zero-byte files are flagged as clutter candidates.
- **Identify large files** — anything over 50 MB is flagged for attention.
- **Highlight old, unused files** — anything untouched for 180+ days is flagged.
- **Move organized files into categorized folders** — well, *copy* them — originals are never moved.
- **Never overwrite originals** — if a name collision would occur, the copy is automatically renamed instead.
- **Never delete immediately** — nothing is ever deleted by this app. Duplicates are only ever *recommended* for deletion, and copied into a clearly separated folder for you to review by hand.
</div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
<div class="section-card">
<h4>Why this order matters</h4>

1. **Backup first** — so there's a safety net before anything else happens, even against synthetic data.
2. **Scan second** — to understand what's actually there before making any decisions.
3. **Plan third** — every operation is written down and shown to you before it happens (the dry run).
4. **Approve fourth** — you explicitly confirm you've reviewed the plan.
5. **Execute fifth** — and even then, only as *copies* into a new organized folder — your original mess stays exactly where it was.
</div>
        """,
        unsafe_allow_html=True,
    )

    if st.session_state.scan_result is None:
        st.info("Run the **🔍 Folder Scanner** first to see this brief tailored to your actual data.")
    else:
        sr = st.session_state.scan_result
        st.markdown("#### Applied to your current scan")
        st.write(
            f"Based on the last scan, this pipeline will organize **{sr.total_files} files** "
            f"into **{len(sr.category_breakdown)} categories**, with "
            f"**{len(sr.empty_files)} empty files**, **{len(sr.old_files)} old files**, "
            f"and **{len(st.session_state.duplicate_groups or [])} duplicate groups** flagged for your review."
        )


# ==========================================================================
# PAGE: Dry Run
# ==========================================================================
elif page == "🧪 Dry Run":
    st.title("🧪 Dry Run — Full Execution Plan")
    st.caption("Nothing here is executed. This is a complete preview of every planned operation.")

    if st.session_state.scan_result is None:
        st.warning("Run the **🔍 Folder Scanner** first.")
        st.stop()

    if st.button("🧮 Build execution plan", type="primary"):
        with st.spinner("Building the full dry-run plan..."):
            plan = planner.build_plan(st.session_state.scan_result, st.session_state.duplicate_groups or [])
        st.session_state.plan = plan
        st.session_state.plan_approved = False
        st.success("Plan built. Review it below before approving.")

    plan = st.session_state.plan
    if plan is None:
        st.info("Click **Build execution plan** to generate the dry run.")
        st.stop()

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total operations", plan.total_operations)
    c2.metric("Moves", len(plan.moves))
    c3.metric("Renames (collision-safe)", len(plan.renames))
    c4.metric("Recommended deletes", len(plan.recommended_deletes))

    st.markdown(
        f'<div class="callout">Recommended deletions would reclaim approximately '
        f'<strong>{human_readable_size(plan.reclaimable_bytes)}</strong> — but nothing is ever '
        f"deleted automatically. These files are copied into a separate review folder instead.</div>",
        unsafe_allow_html=True,
    )

    st.divider()

    with st.expander(f"{badge('MOVE', 'move')} File moves ({len(plan.moves)})", expanded=False):
        st.markdown(badge("MOVE", "move"), unsafe_allow_html=True)
        st.dataframe(
            pd.DataFrame([{"Source": e.source, "Destination": e.destination, "Reason": e.reason} for e in plan.moves]),
            use_container_width=True, hide_index=True,
        )

    with st.expander(f"Collision-safe renames ({len(plan.renames)})"):
        st.markdown(badge("RENAME", "rename"), unsafe_allow_html=True)
        if plan.renames:
            st.dataframe(
                pd.DataFrame([{"Original name": e.source, "Renamed to": e.destination, "Reason": e.reason} for e in plan.renames]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("No naming collisions detected in this plan.")

    with st.expander(f"Duplicate content flags ({len(plan.duplicate_flags)})"):
        st.markdown(badge("FLAG", "flag"), unsafe_allow_html=True)
        if plan.duplicate_flags:
            st.dataframe(
                pd.DataFrame([{"File": e.source, "Reason": e.reason} for e in plan.duplicate_flags]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("No content duplicates found.")

    with st.expander(f"Large file flags ({len(plan.large_file_flags)})"):
        st.markdown(badge("FLAG", "flag"), unsafe_allow_html=True)
        if plan.large_file_flags:
            st.dataframe(
                pd.DataFrame([{"File": e.source, "Reason": e.reason} for e in plan.large_file_flags]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("No large files found.")

    with st.expander(f"Old file flags ({len(plan.old_file_flags)})"):
        st.markdown(badge("FLAG", "flag"), unsafe_allow_html=True)
        if plan.old_file_flags:
            st.dataframe(
                pd.DataFrame([{"File": e.source, "Reason": e.reason} for e in plan.old_file_flags]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("No old files found.")

    with st.expander(f"Empty file flags ({len(plan.empty_file_flags)})"):
        st.markdown(badge("FLAG", "flag"), unsafe_allow_html=True)
        if plan.empty_file_flags:
            st.dataframe(
                pd.DataFrame([{"File": e.source, "Reason": e.reason} for e in plan.empty_file_flags]),
                use_container_width=True, hide_index=True,
            )
        else:
            st.write("No empty files found.")

    st.divider()
    st.markdown("#### 🗑️ Recommended for deletion — NOT executed")
    st.markdown(
        '<div class="callout">This section is shown for transparency only. The app will '
        "<strong>never</strong> delete these files. During execution, they are copied into "
        "<code>generated/Organized/_Recommended_For_Deletion/</code> so you can review and "
        "remove them yourself if you agree.</div>",
        unsafe_allow_html=True,
    )
    st.markdown(badge("DELETE — Recommended, not executed", "delete"), unsafe_allow_html=True)
    if plan.recommended_deletes:
        st.dataframe(
            pd.DataFrame([
                {"File": e.source, "Reason": e.reason.split(" | bytes:")[0]}
                for e in plan.recommended_deletes
            ]),
            use_container_width=True, hide_index=True,
        )
    else:
        st.write("Nothing recommended for deletion.")


# ==========================================================================
# PAGE: Execution
# ==========================================================================
elif page == "✅ Execution":
    st.title("✅ Execution")
    st.caption("Copy-only execution. Originals are never modified, moved, or deleted.")

    if st.session_state.plan is None:
        st.warning("Build a plan on the **🧪 Dry Run** page first.")
        st.stop()

    plan = st.session_state.plan

    st.markdown(
        '<div class="callout">Reminder: execution only <strong>copies</strong> files into '
        "<code>generated/Organized/</code>. Your original files in <code>data/Downloads/</code> "
        "and the backup remain completely untouched.</div>",
        unsafe_allow_html=True,
    )

    st.markdown(f"**Plan summary:** {plan.total_operations} total operations — "
                f"{len(plan.moves)} moves, {len(plan.renames)} collision-safe renames, "
                f"{len(plan.recommended_deletes)} items flagged for manual deletion review.")

    approved = st.checkbox("I have reviewed the plan", value=st.session_state.plan_approved)
    st.session_state.plan_approved = approved

    execute_disabled = not approved
    if st.button("🚀 Execute plan", type="primary", disabled=execute_disabled):
        progress = st.progress(0, text="Starting execution...")
        with st.spinner("Copying files into generated/Organized/..."):
            progress.progress(30, text="Copying categorized files...")
            result = organizer.execute_plan(st.session_state.scan_result, st.session_state.duplicate_groups or [])
            progress.progress(100, text="Done.")
        st.session_state.execution_result = result
        if result.errors:
            st.warning(f"Execution finished with {len(result.errors)} error(s). See details below.")
        else:
            st.success(f"Execution complete: {result.files_copied} files copied successfully.")

    if execute_disabled:
        st.caption("Check the box above to enable execution.")

    result = st.session_state.execution_result
    if result:
        st.divider()
        st.subheader("Execution results")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Files copied", result.files_copied)
        c2.metric("Renamed for collision safety", result.files_renamed_on_copy)
        c3.metric("Copied to review folder", result.recommended_deletes_copied)
        c4.metric("Total data copied", human_readable_size(result.bytes_copied))

        st.markdown("#### By category")
        if result.category_counts:
            cat_df = pd.DataFrame(sorted(result.category_counts.items(), key=lambda x: -x[1]), columns=["Category", "Files"])
            st.bar_chart(cat_df.set_index("Category"))

        if result.errors:
            with st.expander(f"⚠️ Errors ({len(result.errors)})"):
                for err in result.errors:
                    st.write(f"- {err}")

        st.info(f"Organized files are available at: `{ORGANIZED_DIR}`")


# ==========================================================================
# PAGE: Reports
# ==========================================================================
elif page == "📊 Reports":
    st.title("📊 Reports")
    st.caption("Generate and download the final summary report bundle.")

    if st.session_state.plan is None:
        st.warning("Build a plan on the **🧪 Dry Run** page first (execution is optional).")
        st.stop()

    if st.button("📝 Generate reports", type="primary"):
        with st.spinner("Writing cleanup_report.csv / .xlsx / .json / .txt ..."):
            paths = reporter.generate_reports(
                st.session_state.scan_result,
                st.session_state.duplicate_groups or [],
                st.session_state.plan,
                st.session_state.execution_result,
            )
        st.session_state.report_paths = paths
        st.success("Reports generated.")

    paths = st.session_state.report_paths
    if not paths:
        st.info("Click **Generate reports** to build the report bundle.")
        st.stop()

    st.divider()
    st.subheader("Summary")

    sr = st.session_state.scan_result
    dup_groups = st.session_state.duplicate_groups or []
    plan = st.session_state.plan
    execution_result = st.session_state.execution_result

    c1, c2, c3 = st.columns(3)
    c1.metric("Files scanned", sr.total_files)
    c2.metric("Duplicate groups", len(dup_groups))
    c3.metric("Space reclaimable", human_readable_size(sum(g.wasted_bytes for g in dup_groups)))

    if execution_result:
        st.markdown(f"✅ **Execution status:** {execution_result.files_copied} files organized into "
                    f"`generated/Organized/`, {execution_result.recommended_deletes_copied} copied to the "
                    f"review-for-deletion folder.")
    else:
        st.markdown("⬜ **Execution status:** Not yet executed — this report reflects the dry-run plan only.")

    st.divider()
    st.subheader("Download reports")

    dl_cols = st.columns(4)
    labels = {"csv": "CSV", "xlsx": "Excel (.xlsx)", "json": "JSON", "txt": "Text summary"}
    mimes = {
        "csv": "text/csv",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "json": "application/json",
        "txt": "text/plain",
    }
    for i, (fmt, path) in enumerate(paths.items()):
        with dl_cols[i % 4]:
            st.download_button(
                label=f"⬇️ {labels.get(fmt, fmt)}",
                data=path.read_bytes(),
                file_name=path.name,
                mime=mimes.get(fmt, "application/octet-stream"),
                use_container_width=True,
            )

    log_path = Path(__file__).resolve().parent / "generated" / "Logs" / "execution_log.txt"
    if log_path.exists():
        with st.expander("📜 View execution_log.txt"):
            st.code(log_path.read_text(encoding="utf-8"), language="text")
        st.download_button(
            "⬇️ execution_log.txt",
            data=log_path.read_bytes(),
            file_name="execution_log.txt",
            mime="text/plain",
        )

    st.divider()
    st.subheader("Report preview")
    tab1, tab2 = st.tabs(["File detail (CSV)", "Text summary"])
    with tab1:
        st.dataframe(pd.read_csv(paths["csv"]), use_container_width=True, hide_index=True)
    with tab2:
        st.code(paths["txt"].read_text(encoding="utf-8"), language="text")


# ==========================================================================
# PAGE: About Project
# ==========================================================================
elif page == "ℹ️ About Project":
    st.title("ℹ️ About This Project")

    st.markdown(
        """
<div class="section-card">
<h4>What this is</h4>
Organize Mess is a safe file-organization assistant built for Task 4 of the assignment:
"Organize the Mess (The Files You Forgot)". Rather than pointing at a real personal folder,
it generates a realistic synthetic <code>Downloads/</code> folder so there is nothing real
to lose — but it still walks through every safety step a production tool would need:
backup, scan, plan, approve, execute (copy-only), and report.
</div>

<div class="section-card">
<h4>Safety mechanism</h4>

1. **Backup** — the entire source folder is copied verbatim before anything else happens.
2. **Dry run** — every move, rename, flag, and recommended-delete operation is computed and shown in full, before anything is touched.
3. **Explicit approval** — a checkbox gate ("I have reviewed the plan") must be ticked before the Execute button is even enabled.
4. **Copy-only execution** — organized output is always a *copy*; originals in both the source folder and the backup are never modified, moved, or deleted.
5. **No automatic deletion** — duplicate files are only ever recommended for deletion and copied into a clearly separated review folder. Deleting them is left entirely to the human.
</div>

<div class="section-card">
<h4>Reusability — pointing this at a different folder later</h4>
Everything in this app is derived from a single constant in <code>modules/utils.py</code>:

```python
SOURCE_DIR = BASE_DIR / "data" / "Downloads"
```

To reuse this tool on a real folder later, change that one path (and optionally skip the
dummy-data generation step on the Dashboard). The backup path, organized output, and
report locations are all derived automatically — nothing else in the codebase needs to change.
</div>

<div class="section-card">
<h4>Dummy dataset</h4>
The synthetic <code>Downloads/</code> folder includes ~100-150 files: PDFs, Word/Excel/PowerPoint
stand-ins, ZIPs, text, CSV, JSON, images, videos, music, Python/HTML files, and nested folders.
It deliberately includes exact duplicate files, same-name/different-content collisions,
same-content/different-name duplicates, empty files, and oversized files, so every detection
path in the pipeline has real data to work against.
</div>

<div class="section-card">
<h4>Tech stack</h4>
Python 3.12+, Streamlit, pathlib, hashlib, shutil, pandas, and openpyxl for the Excel report.
No database required — everything operates on the local filesystem inside this project folder.
</div>

<div class="section-card">
<h4>Future improvements</h4>

- Configurable category rules via a settings page instead of editing utils.py directly
- Scheduled / recurring scans with historical trend charts
- Optional integration with a real trash/recycle bin API for user-approved deletions
- Multi-folder support (organize several source folders in one run)
- Content-aware categorization (e.g. OCR-based sorting of scanned receipts vs. photos)
</div>
        """,
        unsafe_allow_html=True,
    )
