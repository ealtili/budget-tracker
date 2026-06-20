import os

import streamlit as st

st.set_page_config(
    page_title="Budget Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

if not os.environ.get("APP_SECRET_KEY"):
    st.error(
        "**Configuration error:** `APP_SECRET_KEY` is not set.\n\n"
        "Generate a key with:\n"
        "```\n"
        "python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\"\n"
        "```"
    )
    st.stop()

from budget_tracker.auth.auth_service import is_admin  # noqa: E402
from budget_tracker.ui import (  # noqa: E402
    add_transaction_page,
    admin_page,
    dashboard_page,
    expenses_page,
    income_page,
    login_page,
    settings_page,
    upload_page,
)
from budget_tracker.ui.theme import apply_theme, render_selector  # noqa: E402

_USER_PAGES = {
    "📊 Overview":        dashboard_page,
    "💸 Expenses":        expenses_page,
    "💰 Income":          income_page,
    "➕ Add Transaction": add_transaction_page,
    "📂 Upload":          upload_page,
    "⚙️ Settings":        settings_page,
}

_ADMIN_PAGES = {
    "👑 Admin Panel":     admin_page,
    "⚙️ Settings":        settings_page,
}


def main() -> None:
    apply_theme()

    if not st.session_state.get("authenticated"):
        login_page.render()
        return

    # Forced password change — block access to the rest of the app
    if st.session_state.get("must_change_password"):
        login_page.render_force_change()
        return

    username  = st.session_state.get("username", "")
    user_is_admin = is_admin(username)

    pages = _ADMIN_PAGES if user_is_admin else _USER_PAGES

    with st.sidebar:
        st.title("💰 Budget Tracker")
        if user_is_admin:
            st.caption("👑 Admin")
        else:
            st.write(f"👤 **{st.session_state.get('display_name', 'User')}**")
            st.caption(f"@{username}")
        st.divider()

        page_label = st.radio(
            "Navigation",
            list(pages.keys()),
            label_visibility="collapsed",
        )

        st.divider()
        render_selector(compact=True)

        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    pages[page_label].render()


if __name__ == "__main__":
    main()
