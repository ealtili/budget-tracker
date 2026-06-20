import pandas as pd
import streamlit as st

from budget_tracker.ingestion.parser import (
    COLUMN_ALIASES,
    REQUIRED_COLUMNS,
    apply_mapping,
    detect_mapping,
    parse_file,
)
from budget_tracker.ingestion.templates import EXPECTED_COLUMNS, generate_template_csv
from budget_tracker.ingestion.validator import validate_rows
from budget_tracker.storage.transaction_store import add_transactions_bulk


def _guard() -> None:
    if not st.session_state.get("authenticated"):
        st.stop()


def _clear_import_state() -> None:
    for key in ("import_valid", "import_errors", "import_df", "import_mapping", "import_source"):
        st.session_state.pop(key, None)


def render() -> None:
    _guard()
    st.title("📂 Upload Transactions")

    # ── Phase 0: Instructions & template ─────────────────────────────────────
    with st.expander("📋 Expected Format & Instructions", expanded=True):
        st.markdown(
            "Upload a **CSV** or **Excel (.xlsx)** file. "
            "The file must have at least **date**, **type**, and **amount** columns. "
            "Column names are matched automatically — see the alias list below."
        )

        col_df = pd.DataFrame(
            EXPECTED_COLUMNS, columns=["Column", "Required", "Format / Values"]
        )
        st.table(col_df)

        st.download_button(
            "⬇️ Download CSV Template",
            data=generate_template_csv(),
            file_name="budget_tracker_template.csv",
            mime="text/csv",
        )

    uploaded = st.file_uploader(
        "Choose a file", type=["csv", "xlsx"], on_change=_clear_import_state
    )

    if not uploaded:
        return

    # ── Phase 1: Parse ────────────────────────────────────────────────────────
    file_bytes = uploaded.read()
    try:
        raw_df, auto_mapping = parse_file(file_bytes, uploaded.name)
    except ValueError as exc:
        st.error(f"Could not read file: {exc}")
        return

    st.success(f"File loaded — **{len(raw_df)} rows** detected.")

    with st.expander("Preview (first 5 rows of raw file)"):
        st.dataframe(raw_df.head(5), use_container_width=True)

    # ── Phase 2: Column mapping ───────────────────────────────────────────────
    st.subheader("Column Mapping")

    unresolved = [field for field, col in auto_mapping.items() if col is None]
    final_mapping = dict(auto_mapping)
    df_cols_with_skip = ["(skip)"] + list(raw_df.columns)

    if not unresolved:
        detected = {k: v for k, v in auto_mapping.items() if v is not None}
        st.success("All columns detected automatically:")
        st.json(detected, expanded=False)
    else:
        st.warning(
            f"Could not auto-detect: **{', '.join(unresolved)}**. "
            "Map them below, or skip optional ones."
        )
        for field in unresolved:
            required = field in REQUIRED_COLUMNS
            label = (
                f"{'⚠️ Required — ' if required else 'Optional — '}"
                f"Your column for `{field}`"
            )
            chosen = st.selectbox(label, df_cols_with_skip, key=f"map_{field}")
            final_mapping[field] = None if chosen == "(skip)" else chosen

    missing_required = [f for f in REQUIRED_COLUMNS if not final_mapping.get(f)]
    if missing_required:
        st.error(
            f"Required columns are still unmapped: **{', '.join(missing_required)}**. "
            "Cannot proceed until these are assigned."
        )
        return

    # ── Phase 3: Validate ─────────────────────────────────────────────────────
    if st.button("🔍 Validate Rows", use_container_width=True):
        source = "excel_upload" if uploaded.name.lower().endswith(".xlsx") else "csv_upload"
        mapped_df = apply_mapping(raw_df, final_mapping)
        valid_rows, error_rows = validate_rows(mapped_df, source=source)
        st.session_state["import_valid"] = valid_rows
        st.session_state["import_errors"] = error_rows
        st.session_state["import_source"] = source

    if "import_valid" not in st.session_state:
        return

    valid_rows: list[dict] = st.session_state["import_valid"]
    error_rows: list[dict] = st.session_state["import_errors"]

    # ── Phase 4: Review & decision ────────────────────────────────────────────
    st.divider()
    st.subheader("Validation Results")

    m1, m2 = st.columns(2)
    m1.metric("✅ Ready to import", len(valid_rows))
    m2.metric("❌ Rows with issues", len(error_rows))

    if error_rows:
        with st.expander(f"Show {len(error_rows)} invalid row(s)"):
            err_df = pd.DataFrame(error_rows)
            st.dataframe(err_df, use_container_width=True, hide_index=True)

        error_csv = pd.DataFrame(error_rows).to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Download Error Report (.csv)",
            data=error_csv,
            file_name="import_errors.csv",
            mime="text/csv",
        )

    if not valid_rows:
        st.error("No valid rows to import. Fix the issues in your file and try again.")
        return

    # ── Phase 5: Import ───────────────────────────────────────────────────────
    col_import, col_cancel = st.columns(2)

    with col_import:
        if st.button(
            f"✅ Import {len(valid_rows)} valid row(s)",
            use_container_width=True,
            type="primary",
        ):
            user_id: str = st.session_state["user_id"]
            try:
                count = add_transactions_bulk(user_id, valid_rows)
                skipped = len(error_rows)
                _clear_import_state()
                st.success(
                    f"**{count}** transaction(s) imported successfully. "
                    + (f"**{skipped}** row(s) were skipped." if skipped else "")
                )
                st.balloons()
            except Exception as exc:
                st.error(f"Import failed: {exc}")

    with col_cancel:
        if st.button("Cancel", use_container_width=True):
            _clear_import_state()
            st.rerun()
