import streamlit as st

from budget_tracker.auth.auth_service import change_password, delete_account
from budget_tracker.storage.transaction_store import delete_user_store, get_transactions
from budget_tracker.ui.theme import render_selector


def _guard() -> None:
    if not st.session_state.get("authenticated"):
        st.stop()


def render() -> None:
    _guard()
    st.title("⚙️ Settings")

    user_id: str = st.session_state["user_id"]
    username: str = st.session_state["username"]
    display_name: str = st.session_state["display_name"]

    st.subheader(f"{display_name}")
    st.caption(f"@{username}")
    st.divider()

    # ── Appearance ────────────────────────────────────────────────────────────
    st.subheader("🎨 Appearance")
    st.caption("Choose a theme. **System** follows your OS light/dark preference.")
    render_selector(compact=False)

    st.divider()

    # ── Change password ───────────────────────────────────────────────────────
    st.subheader("🔑 Change Password")
    with st.form("change_password_form"):
        current_pw = st.text_input("Current Password", type="password")
        new_pw = st.text_input(
            "New Password", type="password", help="Minimum 8 characters"
        )
        confirm_pw = st.text_input("Confirm New Password", type="password")
        submitted_pw = st.form_submit_button("Update Password", type="primary")

    if submitted_pw:
        if not current_pw or not new_pw:
            st.error("Please fill in all password fields.")
        elif new_pw != confirm_pw:
            st.error("New passwords do not match.")
        else:
            try:
                change_password(user_id, current_pw, new_pw)
                st.success("Password updated successfully.")
            except ValueError as exc:
                st.error(str(exc))

    st.divider()

    # ── Download data ─────────────────────────────────────────────────────────
    st.subheader("⬇️ Download My Data")
    try:
        transactions = get_transactions(user_id)
    except ValueError:
        transactions = []

    if transactions:
        import pandas as pd

        # Explicit column order — logical for a human reading the CSV.
        # Internal fields (id) are excluded; missing columns are silently skipped.
        _EXPORT_COLS = [
            "date", "time", "type", "category", "description",
            "amount", "currency", "source", "created_at",
        ]
        df = pd.DataFrame(transactions)
        ordered_cols = [c for c in _EXPORT_COLS if c in df.columns]
        csv_data = df[ordered_cols].to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download all transactions (.csv)",
            data=csv_data,
            file_name=f"{username}_transactions.csv",
            mime="text/csv",
        )
        st.caption(f"{len(transactions)} transaction(s) on file.")
    else:
        st.info("No transactions to export yet.")

    st.divider()

    # ── Delete account ────────────────────────────────────────────────────────
    st.subheader("🗑️ Delete Account")
    st.warning(
        "**Permanent action.** All your transactions will be deleted and cannot be recovered.",
        icon="⚠️",
    )

    with st.form("delete_account_form"):
        st.write(f"Type your username **`{username}`** to confirm:")
        confirm_input = st.text_input("Username confirmation")
        submitted_del = st.form_submit_button("Delete My Account", type="primary")

    if submitted_del:
        try:
            delete_account(user_id, confirm_input)
            delete_user_store(user_id)
            st.session_state.clear()
            st.success("Account deleted. Goodbye.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))
