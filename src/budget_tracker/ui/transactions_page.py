from datetime import date, datetime

import pandas as pd
import streamlit as st

from budget_tracker.ingestion.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES
from budget_tracker.ingestion.validator import _sanitize_description
from budget_tracker.storage.transaction_store import (
    delete_transaction,
    get_transactions,
    update_transaction,
)

_INCOME_OPTIONS = [f"💰 {c}" for c in INCOME_CATEGORIES]
_EXPENSE_OPTIONS = [f"💸 {c}" for c in EXPENSE_CATEGORIES]
_ALL_OPTIONS = _INCOME_OPTIONS + _EXPENSE_OPTIONS
_OPTION_META: dict[str, tuple[str, str]] = {
    **{f"💰 {c}": ("income", c) for c in INCOME_CATEGORIES},
    **{f"💸 {c}": ("expense", c) for c in EXPENSE_CATEGORIES},
}
_META_REVERSE: dict[tuple[str, str], str] = {v: k for k, v in _OPTION_META.items()}


def _guard() -> None:
    if not st.session_state.get("authenticated"):
        st.stop()


def _load_df(user_id: str) -> pd.DataFrame | None:
    try:
        txns = get_transactions(user_id)
    except ValueError as exc:
        st.error(f"Could not load transactions: {exc}")
        return None
    if not txns:
        st.info("No transactions yet. Add one manually or upload a file.")
        return None
    df = pd.DataFrame(txns)
    df["date"] = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    if "time" not in df.columns:
        df["time"] = "00:00:00"
    if "description" not in df.columns:
        df["description"] = ""
    return df


def _edit_form(txn: dict) -> None:
    st.subheader("Edit Transaction")

    # Category outside form so the type badge updates on change
    current_label = _META_REVERSE.get((txn["type"], txn["category"]), _ALL_OPTIONS[0])
    selected_label = st.selectbox(
        "Category",
        _ALL_OPTIONS,
        index=_ALL_OPTIONS.index(current_label),
        key="edit_category",
        help="💰 = Income  ·  💸 = Expense",
    )
    new_type, new_category = _OPTION_META[selected_label]
    if new_type == "income":
        st.success(f"Type: **Income**", icon="💰")
    else:
        st.error(f"Type: **Expense**", icon="💸")

    with st.form("edit_txn_form"):
        c1, c2 = st.columns(2)
        with c1:
            new_amount = st.number_input(
                "Amount ($)",
                min_value=0.01,
                max_value=9_999_999.00,
                value=float(txn["amount"]),
                step=0.01,
                format="%.2f",
            )
            new_date = st.date_input(
                "Date",
                value=date.fromisoformat(txn["date"][:10]),
                max_value=date.today(),
            )
        with c2:
            new_time = st.text_input(
                "Time (HH:MM:SS)",
                value=txn.get("time", "00:00:00"),
                max_chars=8,
            )
            new_desc = st.text_input(
                "Description",
                value=txn.get("description", ""),
                max_chars=200,
            )

        col_save, col_cancel = st.columns(2)
        with col_save:
            submitted = st.form_submit_button("Save Changes", type="primary", use_container_width=True)
        with col_cancel:
            cancelled = st.form_submit_button("Cancel", use_container_width=True)

    if cancelled:
        st.session_state.pop("editing_id", None)
        st.rerun()

    if submitted:
        try:
            parsed_time = datetime.strptime(new_time.strip(), "%H:%M:%S")
        except ValueError:
            st.error("Invalid time format — use HH:MM:SS.")
            return

        updates = {
            "type":        new_type,
            "category":    new_category,
            "amount":      round(float(new_amount), 2),
            "date":        new_date.isoformat(),
            "time":        parsed_time.strftime("%H:%M:%S"),
            "description": _sanitize_description(new_desc),
        }
        try:
            update_transaction(st.session_state["user_id"], txn["id"], updates)
            st.toast("✅ Transaction updated.")
            st.session_state.pop("editing_id", None)
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))


def render() -> None:
    _guard()
    st.title("📋 Transactions")

    user_id = st.session_state["user_id"]
    df = _load_df(user_id)
    if df is None:
        return

    # ── Filters ───────────────────────────────────────────────────────────────
    today = date.today()
    dr1, dr2 = st.columns(2)
    with dr1:
        start_date = st.date_input("From", value=date(today.year, today.month, 1), key="txn_from")
    with dr2:
        end_date = st.date_input("To", value=today, key="txn_to")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        search = st.text_input("Search description", placeholder="e.g. lunch", key="txn_search")
    with fc2:
        type_filter = st.selectbox("Type", ["All", "Income", "Expense"], key="txn_type")
    with fc3:
        all_cats = sorted(df["category"].unique().tolist())
        cat_filter = st.selectbox("Category", ["All"] + all_cats, key="txn_cat")

    disp = df.copy()
    disp = disp[(disp["date"].dt.date >= start_date) & (disp["date"].dt.date <= end_date)]
    if search:
        disp = disp[disp["description"].str.contains(search, case=False, na=False)]
    if type_filter != "All":
        disp = disp[disp["type"] == type_filter.lower()]
    if cat_filter != "All":
        disp = disp[disp["category"] == cat_filter]

    disp = disp.sort_values("date", ascending=False)

    # Keep original index aligned to txn id for selection lookup
    disp = disp.reset_index(drop=True)

    display_cols = ["date", "time", "type", "category", "description", "amount", "currency"]
    available = [c for c in display_cols if c in disp.columns]
    col_labels = {
        "date": "Date", "time": "Time", "type": "Type",
        "category": "Category", "description": "Description",
        "amount": "Amount ($)", "currency": "Currency",
    }
    render_df = disp[available].copy()
    render_df["date"] = render_df["date"].dt.strftime("%Y-%m-%d")
    render_df = render_df.rename(columns=col_labels)

    st.caption(f"{len(disp)} transaction(s)")
    event = st.dataframe(
        render_df,
        use_container_width=True,
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key="txn_table",
    )

    selected_rows = event.selection.rows
    if not selected_rows:
        st.info("Select a row to edit or delete it.")
        return

    selected_idx = selected_rows[0]
    if selected_idx >= len(disp):
        st.info("Select a row to edit or delete it.")
        return
    txn_id = disp.iloc[selected_idx]["id"]
    # Fetch the live record (disp row already has all fields but may be stale after edit)
    all_txns = get_transactions(user_id)
    txn = next((t for t in all_txns if t["id"] == txn_id), None)
    if txn is None:
        st.warning("Selected transaction no longer exists.")
        return

    st.divider()

    # ── Action buttons ────────────────────────────────────────────────────────
    editing = st.session_state.get("editing_id") == txn_id
    confirm_delete = st.session_state.get("confirm_delete_id") == txn_id

    ba, bb = st.columns(2)
    with ba:
        if st.button("✏️ Edit", key="btn_edit", use_container_width=True):
            st.session_state["editing_id"] = txn_id
            st.session_state.pop("confirm_delete_id", None)
            st.rerun()
    with bb:
        if st.button("🗑️ Delete", key="btn_delete", use_container_width=True, type="secondary"):
            st.session_state["confirm_delete_id"] = txn_id
            st.session_state.pop("editing_id", None)
            st.rerun()

    if confirm_delete:
        st.warning(
            f"Delete **{txn['category']}** — **${txn['amount']:,.2f}** on {txn['date'][:10]}? "
            "This cannot be undone."
        )
        cd1, cd2 = st.columns(2)
        with cd1:
            if st.button("Confirm Delete", type="primary", use_container_width=True, key="confirm_del_yes"):
                try:
                    delete_transaction(user_id, txn_id)
                    st.toast("🗑️ Transaction deleted.")
                    st.session_state.pop("confirm_delete_id", None)
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
        with cd2:
            if st.button("Cancel", use_container_width=True, key="confirm_del_no"):
                st.session_state.pop("confirm_delete_id", None)
                st.rerun()

    if editing:
        st.divider()
        _edit_form(txn)
