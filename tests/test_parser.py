import io

import pandas as pd
import pytest

from budget_tracker.ingestion.parser import (
    REQUIRED_COLUMNS,
    apply_mapping,
    detect_mapping,
    parse_file,
)


def _csv(content: str) -> bytes:
    return content.encode("utf-8")


# ── detect_mapping ────────────────────────────────────────────────────────────

def test_exact_column_names_detected():
    mapping = detect_mapping(["date", "type", "amount", "category"])
    assert mapping["date"] == "date"
    assert mapping["type"] == "type"
    assert mapping["amount"] == "amount"
    assert mapping["category"] == "category"


def test_alias_transaction_date_detected():
    mapping = detect_mapping(["Transaction Date", "Amt", "Direction", "Memo"])
    assert mapping["date"] == "Transaction Date"
    assert mapping["amount"] == "Amt"
    assert mapping["type"] == "Direction"
    assert mapping["description"] == "Memo"


def test_unrecognised_columns_map_to_none():
    mapping = detect_mapping(["foo", "bar", "baz"])
    assert all(v is None for v in mapping.values())


def test_case_insensitive_detection():
    mapping = detect_mapping(["DATE", "TYPE", "AMOUNT"])
    assert mapping["date"] == "DATE"
    assert mapping["type"] == "TYPE"
    assert mapping["amount"] == "AMOUNT"


# ── parse_file ────────────────────────────────────────────────────────────────

def test_parse_valid_csv():
    content = _csv("date,type,amount\n2026-06-01,expense,50.00\n")
    df, mapping = parse_file(content, "test.csv")
    assert len(df) == 1
    assert mapping["date"] == "date"
    assert mapping["amount"] == "amount"


def test_parse_rejects_unsupported_extension():
    with pytest.raises(ValueError, match="Only .csv and .xlsx"):
        parse_file(b"data", "file.txt")


def test_parse_rejects_empty_csv():
    with pytest.raises(ValueError, match="no data"):
        parse_file(_csv("date,type,amount\n"), "empty.csv")


# ── apply_mapping ─────────────────────────────────────────────────────────────

def test_apply_mapping_renames_columns():
    df = pd.DataFrame([{"Transaction Date": "2026-06-01", "Amt": "50", "Direction": "expense"}])
    mapping = {"date": "Transaction Date", "amount": "Amt", "type": "Direction",
               "category": None, "description": None, "currency": None}
    result = apply_mapping(df, mapping)
    assert "date" in result.columns
    assert "amount" in result.columns
    assert "Transaction Date" not in result.columns


def test_apply_mapping_drops_unmapped_source_columns():
    df = pd.DataFrame([{"date": "2026-06-01", "amount": "10", "type": "income", "junk": "ignored"}])
    mapping = {"date": "date", "amount": "amount", "type": "type",
               "category": None, "description": None, "currency": None}
    result = apply_mapping(df, mapping)
    assert "junk" not in result.columns
