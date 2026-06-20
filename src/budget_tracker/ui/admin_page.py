"""Admin panel — user management only. No transaction data is visible here."""

import streamlit as st

from budget_tracker.auth.auth_service import (
    admin_delete_user,
    admin_list_users,
    admin_reset_user_password,
    change_password,
    is_admin,
)
from budget_tracker.storage.transaction_store import delete_user_store


def _guard() -> None:
    if not st.session_state.get("authenticated"):
        st.stop()
    if not is_admin(st.session_state.get("username", "")):
        st.error("⛔ Access denied — admin only.")
        st.stop()


def render() -> None:
    _guard()
    st.title("👑 Admin Panel")
    st.caption("User management only. Transaction data is never visible here.")

    users = admin_list_users()

    # ── Summary ───────────────────────────────────────────────────────────────
    locked  = sum(1 for u in users if u.get("locked_until"))
    pending = sum(1 for u in users if u.get("password_reset_required"))

    m1, m2, m3 = st.columns(3)
    m1.metric("Total Users",           len(users))
    m2.metric("Locked Accounts",       locked)
    m3.metric("Pending Password Reset", pending)

    st.divider()

    # ── User list ─────────────────────────────────────────────────────────────
    st.subheader("Registered Users")

    if not users:
        st.info("No regular users registered yet.")
    else:
        for user in users:
            label = f"@{user['username']}  —  {user['display_name']}"
            if user.get("locked_until"):
                label += "  🔒"
            if user.get("password_reset_required"):
                label += "  ⚠️ reset pending"

            with st.expander(label):
                info_col, action_col = st.columns([2, 1])

                with info_col:
                    st.write(f"**Display name:** {user['display_name']}")
                    st.write(f"**Registered:** {user['created_at'][:10]}")
                    st.write(f"**Failed logins:** {user['failed_login_attempts']}")
                    if user.get("locked_until"):
                        st.warning(f"Locked until: `{user['locked_until'][:19]}`")
                    if user.get("password_reset_required"):
                        st.warning("Password reset required on next login.")

                with action_col:
                    reset_key  = f"reset_{user['username']}"
                    confirm_key = f"confirm_del_{user['username']}"

                    if st.button("🔑 Reset Password", key=reset_key, use_container_width=True):
                        try:
                            temp_pw = admin_reset_user_password(user["username"])
                            st.success(
                                f"Temporary password set. Share this with the user — "
                                f"it is shown **once only**:\n\n"
                                f"```\n{temp_pw}\n```"
                            )
                        except ValueError as exc:
                            st.error(str(exc))

                    if not st.session_state.get(confirm_key):
                        if st.button(
                            "🗑️ Delete User", key=f"del_{user['username']}",
                            use_container_width=True,
                        ):
                            st.session_state[confirm_key] = True
                            st.rerun()
                    else:
                        st.warning(f"Delete **@{user['username']}** permanently?")
                        y_col, n_col = st.columns(2)
                        if y_col.button("Yes, delete", key=f"yes_{user['username']}",
                                        use_container_width=True, type="primary"):
                            try:
                                uid = admin_delete_user(user["username"])
                                delete_user_store(uid)
                                st.session_state.pop(confirm_key, None)
                                st.success(f"User @{user['username']} deleted.")
                                st.rerun()
                            except ValueError as exc:
                                st.error(str(exc))
                        if n_col.button("Cancel", key=f"no_{user['username']}",
                                        use_container_width=True):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()

    st.divider()

    # ── Admin change own password ─────────────────────────────────────────────
    st.subheader("🔑 Change Your Admin Password")
    with st.form("admin_pw_form"):
        cur_pw  = st.text_input("Current Password", type="password")
        new_pw  = st.text_input("New Password", type="password", help="Min 8 characters")
        new_pw2 = st.text_input("Confirm New Password", type="password")
        sub     = st.form_submit_button("Update Password", type="primary")

    if sub:
        if not cur_pw or not new_pw:
            st.error("Please fill in all fields.")
        elif new_pw != new_pw2:
            st.error("New passwords do not match.")
        else:
            try:
                change_password(st.session_state["user_id"], cur_pw, new_pw)
                st.success("Admin password updated.")
            except ValueError as exc:
                st.error(str(exc))
