import streamlit as st

from budget_tracker.auth.auth_service import login, register, set_new_password


def render() -> None:
    st.title("💰 Budget Tracker")
    st.subheader("Personal Finance Manager")
    st.write("")

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        tab_login, tab_register = st.tabs(["🔑 Login", "✨ Create Account"])

        with tab_login:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button(
                    "Login", use_container_width=True, type="primary"
                )

            if submitted:
                if not username or not password:
                    st.error("Please enter your username and password.")
                else:
                    user = login(username, password)
                    if user:
                        st.session_state["authenticated"]  = True
                        st.session_state["user_id"]        = user["user_id"]
                        st.session_state["username"]       = user["username"]
                        st.session_state["display_name"]   = user["display_name"]
                        if user.get("password_reset_required"):
                            st.session_state["must_change_password"] = True
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with tab_register:
            with st.form("register_form"):
                display_name   = st.text_input("Display Name", placeholder="Alice")
                new_username   = st.text_input(
                    "Username", placeholder="alice",
                    help="3–32 characters: lowercase letters, numbers, _ or -",
                )
                new_password   = st.text_input(
                    "Password", type="password", help="Minimum 8 characters"
                )
                confirm_password = st.text_input("Confirm Password", type="password")
                submitted_reg  = st.form_submit_button(
                    "Create Account", use_container_width=True, type="primary"
                )

            if submitted_reg:
                if new_password != confirm_password:
                    st.error("Passwords do not match.")
                else:
                    try:
                        user = register(new_username, new_password, display_name)
                        st.session_state["authenticated"] = True
                        st.session_state["user_id"]       = user["user_id"]
                        st.session_state["username"]      = user["username"]
                        st.session_state["display_name"]  = user["display_name"]
                        st.rerun()
                    except ValueError as exc:
                        st.error(str(exc))


def render_force_change() -> None:
    """Shown when admin has reset the user's password and a new one is required."""
    st.title("🔑 Set a New Password")
    st.warning(
        "Your password has been reset by an administrator. "
        "Please set a new password before continuing.",
        icon="⚠️",
    )

    _, col, _ = st.columns([1, 1.6, 1])
    with col:
        with st.form("force_change_form"):
            new_pw  = st.text_input("New Password", type="password", help="Min 8 characters")
            new_pw2 = st.text_input("Confirm New Password", type="password")
            sub     = st.form_submit_button("Set Password", use_container_width=True, type="primary")

        if sub:
            if new_pw != new_pw2:
                st.error("Passwords do not match.")
            else:
                try:
                    set_new_password(st.session_state["user_id"], new_pw)
                    st.session_state.pop("must_change_password", None)
                    st.success("Password updated. Taking you to the app…")
                    st.rerun()
                except ValueError as exc:
                    st.error(str(exc))
