from datetime import date, datetime

import streamlit as st

from budget_tracker.ingestion.categories import EXPENSE_CATEGORIES, INCOME_CATEGORIES
from budget_tracker.ingestion.validator import _sanitize_description
from budget_tracker.storage.transaction_store import add_transaction

# Build a flat ordered list: income first, then expense — each prefixed for scanning
_INCOME_OPTIONS = [f"💰 {c}" for c in INCOME_CATEGORIES]
_EXPENSE_OPTIONS = [f"💸 {c}" for c in EXPENSE_CATEGORIES]
_ALL_OPTIONS = _INCOME_OPTIONS + _EXPENSE_OPTIONS

# Reverse lookup: display label → (type, bare category name)
_OPTION_META: dict[str, tuple[str, str]] = {}
for c in INCOME_CATEGORIES:
    _OPTION_META[f"💰 {c}"] = ("income", c)
for c in EXPENSE_CATEGORIES:
    _OPTION_META[f"💸 {c}"] = ("expense", c)


def _guard() -> None:
    if not st.session_state.get("authenticated"):
        st.stop()


def render() -> None:
    _guard()
    st.title("➕ Add Transaction")

    # ── Category picker (outside form so type badge updates on change) ────────
    selected_label = st.selectbox(
        "Category",
        _ALL_OPTIONS,
        help="💰 = Income source  ·  💸 = Expense category",
    )
    txn_type, bare_category = _OPTION_META[selected_label]

    # Type badge — derived automatically, no manual radio needed
    if txn_type == "income":
        st.success(f"Type detected: **Income**", icon="💰")
    else:
        st.error(f"Type detected: **Expense**", icon="💸")

    st.write("")  # spacing

    with st.form("add_transaction_form", clear_on_submit=True):
        col_left, col_right = st.columns(2)

        with col_left:
            amount = st.number_input(
                "Amount ($)",
                min_value=0.01,
                max_value=9_999_999.00,
                step=0.01,
                format="%.2f",
            )
            txn_date = st.date_input(
                "Date", value=date.today(), max_value=date.today()
            )

        with col_right:
            # Text input for time — st.time_input enforces a 60-second minimum step
            # so we use a plain text field to allow full HH:MM:SS precision.
            time_str = st.text_input(
                "Time (HH:MM:SS)",
                value=datetime.now().strftime("%H:%M:%S"),
                max_chars=8,
                help="Pre-filled with current system time. Edit if logging a past transaction.",
            )
            description = st.text_input(
                "Description (optional)",
                max_chars=200,
                placeholder="e.g. Lunch with colleagues",
            )

        submitted = st.form_submit_button(
            "Add Transaction", use_container_width=True, type="primary"
        )

    if submitted:
        if amount <= 0:
            st.error("Amount must be greater than zero.")
            return

        # Validate and normalise the time string
        try:
            parsed_time = datetime.strptime(time_str.strip(), "%H:%M:%S")
            recorded_time = parsed_time.strftime("%H:%M:%S")
        except ValueError:
            st.error("Invalid time format — please use HH:MM:SS (e.g. 14:30:00).")
            return

        txn = {
            "type":        txn_type,
            "amount":      round(float(amount), 2),
            "category":    bare_category,
            "date":        txn_date.isoformat(),
            "time":        recorded_time,
            "description": _sanitize_description(description),
            "currency":    "USD",
            "source":      "manual",
        }
        try:
            add_transaction(st.session_state["user_id"], txn)
            st.toast(f"✅ {txn_type.title()} of ${amount:.2f} added to '{bare_category}'")
            st.success(
                f"Recorded **{txn_type}** of **${amount:,.2f}** "
                f"in **{bare_category}** on {txn_date} at {recorded_time}."
            )
        except Exception as exc:
            st.error(f"Failed to save transaction: {exc}")
