import io
import re
from typing import Optional

import pandas as pd

COLUMN_ALIASES: dict[str, list[str]] = {
    "date": [
        "date", "transaction date", "txn date", "trans date",
        "value date", "posting date", "when",
    ],
    "time": [
        "time", "transaction time", "txn time", "hour",
        "timestamp", "hh mm ss", "time of transaction",
    ],
    "type": [
        "type", "transaction type", "txn type", "direction",
        "flow", "debit credit", "dr cr",
    ],
    "amount": [
        "amount", "amt", "sum", "value", "price", "cost",
        "debit", "credit", "transaction amount",
    ],
    "category": [
        "category", "cat", "label", "tag", "group",
        "merchant category", "expense type",
    ],
    "description": [
        "description", "desc", "memo", "notes", "note",
        "details", "narrative", "particulars", "reference",
    ],
    "currency": ["currency", "ccy", "curr", "iso currency", "currency code"],
}

REQUIRED_COLUMNS = {"date", "type", "amount"}


def _normalize(header: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", header.lower()).strip()


def detect_mapping(df_columns: list[str]) -> dict[str, Optional[str]]:
    normalized = {col: _normalize(col) for col in df_columns}
    mapping: dict[str, Optional[str]] = {k: None for k in COLUMN_ALIASES}
    used: set[str] = set()

    for canonical, aliases in COLUMN_ALIASES.items():
        for col, norm in normalized.items():
            if col in used:
                continue
            if norm in aliases:
                mapping[canonical] = col
                used.add(col)
                break

    return mapping


def apply_mapping(df: pd.DataFrame, mapping: dict[str, Optional[str]]) -> pd.DataFrame:
    rename = {v: k for k, v in mapping.items() if v is not None}
    df = df.rename(columns=rename)
    keep = [c for c in COLUMN_ALIASES if c in df.columns]
    return df[keep].copy()


def parse_file(file_bytes: bytes, filename: str) -> tuple[pd.DataFrame, dict[str, Optional[str]]]:
    name_lower = filename.lower()
    if name_lower.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(file_bytes))
        except Exception as exc:
            raise ValueError(f"Could not parse CSV: {exc}") from exc
    elif name_lower.endswith(".xlsx"):
        try:
            df = pd.read_excel(io.BytesIO(file_bytes), engine="openpyxl")
        except Exception as exc:
            raise ValueError(f"Could not parse Excel file: {exc}") from exc
    else:
        raise ValueError("Only .csv and .xlsx files are supported")

    if df.empty:
        raise ValueError("The uploaded file contains no data rows")

    mapping = detect_mapping(list(df.columns))
    return df, mapping
