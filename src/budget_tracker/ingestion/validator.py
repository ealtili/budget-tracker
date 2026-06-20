import re
from datetime import date, datetime, time as dt_time
from typing import Any

import pandas as pd
from dateutil import parser as dateutil_parser

from budget_tracker.ingestion.categories import ALL_CATEGORIES, INCOME_CATEGORIES

_HTML_TAG_RE = re.compile(r"<[^>]+>")


# ── Field parsers ─────────────────────────────────────────────────────────────

def _sanitize_description(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = _HTML_TAG_RE.sub("", str(value).strip())
    return text[:200]


def _parse_amount(value: Any) -> float:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("Amount is missing")
    try:
        cleaned = str(value).replace(",", "").replace("$", "").strip()
        amount = float(cleaned)
    except (ValueError, TypeError):
        raise ValueError(f"Cannot parse amount: {value!r}")
    if amount <= 0:
        raise ValueError(f"Amount must be positive, got {amount}")
    if amount > 9_999_999:
        raise ValueError(f"Amount exceeds maximum (9,999,999): {amount}")
    return round(amount, 2)


def _parse_date(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("Date is missing")
    try:
        if isinstance(value, datetime):
            d = value.date()
        elif isinstance(value, date):
            d = value
        else:
            d = dateutil_parser.parse(str(value)).date()
    except Exception:
        raise ValueError(f"Cannot parse date: {value!r}")
    if d > date.today():
        raise ValueError(f"Date {d} is in the future")
    return d.isoformat()


def _parse_time(value: Any) -> str:
    """Parse a time value to HH:MM:SS.

    Accepts HH:MM:SS strings, datetime objects, or full ISO strings.
    Returns "00:00:00" when no time information is available.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "00:00:00"
    if isinstance(value, (datetime,)):
        return value.strftime("%H:%M:%S")
    if isinstance(value, dt_time):
        return value.strftime("%H:%M:%S")
    try:
        text = str(value).strip()
        # Extract time part from full ISO datetime (e.g. "2026-06-15T14:30:00")
        if "T" in text:
            text = text.split("T")[1]
        elif " " in text and len(text) > 10:
            text = text.split(" ")[1]
        # Strip timezone/milliseconds
        text = text[:8]
        parts = text.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        s = int(float(parts[2])) if len(parts) > 2 else 0
        return f"{h:02d}:{m:02d}:{s:02d}"
    except Exception:
        return "00:00:00"


def _parse_type(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        raise ValueError("Type is missing")
    norm = str(value).strip().lower()
    if norm in {"income", "in", "credit", "+", "cr"}:
        return "income"
    if norm in {"expense", "out", "debit", "-", "dr", "expenditure", "payment"}:
        return "expense"
    raise ValueError(f"Type must be 'income' or 'expense', got: {value!r}")


def _parse_category(value: Any, txn_type: str) -> str:
    default = "Other Income" if txn_type == "income" else "Other Expense"
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return default
    title_val = str(value).strip().title()
    if title_val in ALL_CATEGORIES:
        return title_val
    return default


def _parse_currency(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "USD"
    cleaned = re.sub(r"[^A-Za-z]", "", str(value)).upper()
    return cleaned[:3] if cleaned else "USD"


# ── Main validator ────────────────────────────────────────────────────────────

def validate_rows(
    df: pd.DataFrame, source: str = "csv_upload"
) -> tuple[list[dict], list[dict]]:
    valid_rows: list[dict] = []
    error_rows: list[dict] = []

    for i, row in df.iterrows():
        errors: list[str] = []
        txn: dict = {"source": source}

        try:
            txn["type"] = _parse_type(row.get("type"))
        except ValueError as exc:
            errors.append(str(exc))

        try:
            txn["amount"] = _parse_amount(row.get("amount"))
        except ValueError as exc:
            errors.append(str(exc))

        try:
            txn["date"] = _parse_date(row.get("date"))
        except ValueError as exc:
            errors.append(str(exc))

        if errors:
            error_rows.append(
                {
                    "row_number": int(i) + 2,
                    "raw_date": row.get("date", ""),
                    "raw_amount": row.get("amount", ""),
                    "raw_type": row.get("type", ""),
                    "raw_category": row.get("category", ""),
                    "raw_description": row.get("description", ""),
                    "error_reason": "; ".join(errors),
                }
            )
        else:
            # Time: use from data if present, else "00:00:00"
            txn["time"] = _parse_time(row.get("time"))
            txn["category"] = _parse_category(row.get("category"), txn["type"])
            txn["description"] = _sanitize_description(row.get("description"))
            txn["currency"] = _parse_currency(row.get("currency"))
            valid_rows.append(txn)

    return valid_rows, error_rows
