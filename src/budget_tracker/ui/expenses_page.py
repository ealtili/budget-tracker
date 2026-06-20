from datetime import date

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from budget_tracker.storage.transaction_store import get_transactions


def _guard() -> None:
    if not st.session_state.get("authenticated"):
        st.stop()


def render() -> None:
    _guard()
    st.title("💸 Expenses")

    try:
        transactions = get_transactions(st.session_state["user_id"])
    except ValueError as exc:
        st.error(f"Could not load transactions: {exc}")
        return

    expenses = [t for t in transactions if t.get("type") == "expense"]
    if not expenses:
        st.info("No expense transactions yet.")
        return

    df = pd.DataFrame(expenses)
    df["date"]   = pd.to_datetime(df["date"])
    df["amount"] = df["amount"].astype(float)
    if "time" not in df.columns:
        df["time"] = ""

    # ── Date range ────────────────────────────────────────────────────────────
    today = date.today()
    c1, c2 = st.columns(2)
    with c1:
        start_date = st.date_input("From", value=date(today.year, today.month, 1), key="exp_from")
    with c2:
        end_date = st.date_input("To", value=today, key="exp_to")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    mask = (df["date"].dt.date >= start_date) & (df["date"].dt.date <= end_date)
    df = df[mask].copy()
    if df.empty:
        st.info("No expenses in the selected date range.")
        return

    total    = df["amount"].sum()
    avg_day  = df.groupby(df["date"].dt.date)["amount"].sum().mean()
    top_cat  = df.groupby("category")["amount"].sum().idxmax()

    k1, k2, k3 = st.columns(3)
    k1.metric("Total Expenses",      f"${total:,.2f}")
    k2.metric("Avg per Day",         f"${avg_day:,.2f}")
    k3.metric("Top Category",        top_cat)

    st.divider()

    cl, cr = st.columns(2)

    with cl:
        st.subheader("By Category")
        cat_sum = df.groupby("category")["amount"].sum().reset_index().sort_values("amount", ascending=False)
        fig = px.bar(
            cat_sum, x="amount", y="category", orientation="h",
            color="amount", color_continuous_scale="Reds",
            labels={"amount": "Amount ($)", "category": ""},
        )
        fig.update_layout(margin=dict(t=10, b=10, l=0, r=0), coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)

    with cr:
        st.subheader("Category Share")
        fig2 = px.pie(
            cat_sum, values="amount", names="category", hole=0.45,
            color_discrete_sequence=px.colors.sequential.Reds_r,
        )
        fig2.update_layout(margin=dict(t=10, b=10, l=0, r=0))
        fig2.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig2, use_container_width=True)

    st.subheader("Daily Spending Trend")
    daily = df.groupby(df["date"].dt.date)["amount"].sum().reset_index()
    daily.columns = ["date", "amount"]
    fig3 = px.line(
        daily, x="date", y="amount",
        labels={"amount": "Amount ($)", "date": ""},
        color_discrete_sequence=["#EF5350"],
        markers=True,
    )
    fig3.update_layout(margin=dict(t=10, b=10, l=0, r=0))
    st.plotly_chart(fig3, use_container_width=True)

    st.divider()
    st.subheader("Expense Transactions")

    sf, cf = st.columns(2)
    with sf:
        search = st.text_input("Search", placeholder="description...", key="exp_search")
    with cf:
        cats = ["All"] + sorted(df["category"].unique().tolist())
        cat_filter = st.selectbox("Category", cats, key="exp_cat")

    disp = df.copy()
    if search:
        disp = disp[disp["description"].str.contains(search, case=False, na=False)]
    if cat_filter != "All":
        disp = disp[disp["category"] == cat_filter]

    disp = disp.sort_values("date", ascending=False)
    disp["date"] = disp["date"].dt.strftime("%Y-%m-%d")

    col_map = {
        "date": "Date", "time": "Time", "category": "Category",
        "description": "Description", "amount": "Amount ($)", "currency": "Currency",
    }
    available = [c for c in col_map if c in disp.columns]
    st.dataframe(disp[available].rename(columns=col_map), use_container_width=True, hide_index=True)
    st.caption(f"{len(disp)} expense(s) shown — total ${disp['amount'].sum():,.2f}")
