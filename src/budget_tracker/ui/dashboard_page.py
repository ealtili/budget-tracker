from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from budget_tracker.storage.transaction_store import get_transactions


def _guard() -> None:
    if not st.session_state.get("authenticated"):
        st.stop()


def _load_df(user_id: str) -> pd.DataFrame | None:
    try:
        transactions = get_transactions(user_id)
    except ValueError as exc:
        st.error(f"Could not load transactions: {exc}")
        return None
    if not transactions:
        st.info("No transactions yet. Add one manually or upload a file.")
        return None
    df = pd.DataFrame(transactions)
    df["date"]   = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    if "time" not in df.columns:
        df["time"] = ""
    return df


def _date_filter(df: pd.DataFrame) -> pd.DataFrame | None:
    today = date.today()
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("From", value=date(today.year, today.month, 1))
    with c2:
        end_date = st.date_input("To", value=today)
    if start_date > end_date:
        st.error("Start date must be before end date.")
        return None
    mask = (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
    filtered = df[mask].copy()
    if filtered.empty:
        st.info("No transactions in the selected date range.")
        return None
    return filtered


def render() -> None:
    _guard()
    st.title("📊 Overview Dashboard")

    df = _load_df(st.session_state["user_id"])
    if df is None:
        return

    filtered = _date_filter(df)
    if filtered is None:
        return

    income  = filtered.loc[filtered["type"] == "income",  "amount"].sum()
    expense = filtered.loc[filtered["type"] == "expense", "amount"].sum()
    net     = income - expense

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Income",   f"${income:,.2f}")
    k2.metric("Total Expenses", f"${expense:,.2f}")
    k3.metric("Net Savings",    f"${net:,.2f}", delta=f"${net:,.2f}", delta_color="normal")

    st.divider()

    cl, cr = st.columns(2)

    with cl:
        st.subheader("Spending by Category")
        exp_df = filtered[filtered["type"] == "expense"]
        if exp_df.empty:
            st.info("No expense data in range.")
        else:
            cat_sum = exp_df.groupby("category")["amount"].sum().reset_index()
            fig = px.pie(
                cat_sum, values="amount", names="category", hole=0.4,
                color_discrete_sequence=px.colors.qualitative.Safe,
            )
            fig.update_layout(margin=dict(t=10, b=10, l=0, r=0))
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)

    with cr:
        st.subheader("Monthly Income vs Expenses")
        monthly = filtered.copy()
        monthly["month"] = monthly["date"].dt.to_period("M").astype(str)
        msum = monthly.groupby(["month", "type"])["amount"].sum().reset_index()
        if not msum.empty:
            fig2 = px.bar(
                msum, x="month", y="amount", color="type", barmode="group",
                color_discrete_map={"income": "#4CAF50", "expense": "#EF5350"},
                labels={"amount": "Amount ($)", "month": "", "type": ""},
            )
            fig2.update_layout(margin=dict(t=10, b=10, l=0, r=0))
            st.plotly_chart(fig2, use_container_width=True)

    st.divider()
    st.subheader("Transactions")

    sf, tf = st.columns(2)
    with sf:
        search = st.text_input("Search description", placeholder="e.g. lunch")
    with tf:
        type_filter = st.selectbox("Type", ["All", "Income", "Expense"])

    disp = filtered.copy()
    if search:
        disp = disp[disp["description"].str.contains(search, case=False, na=False)]
    if type_filter != "All":
        disp = disp[disp["type"] == type_filter.lower()]

    disp = disp.sort_values("date", ascending=False)
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")

    col_map = {
        "date": "Date", "time": "Time", "type": "Type",
        "category": "Category", "description": "Description",
        "amount": "Amount ($)", "currency": "Currency",
    }
    available = [c for c in col_map if c in disp.columns]
    disp = disp[available].rename(columns=col_map)

    st.dataframe(disp, use_container_width=True, hide_index=True)
    st.caption(f"{len(disp)} transaction(s) shown")
