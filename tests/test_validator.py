import pandas as pd
import pytest

from budget_tracker.ingestion.validator import validate_rows


def _df(rows: list[dict]) -> pd.DataFrame:
    return pd.DataFrame(rows)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_valid_expense_row():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "50.00", "category": "Food & Drink"}])
    valid, errors = validate_rows(df)
    assert len(valid) == 1
    assert len(errors) == 0
    assert valid[0]["amount"] == 50.0
    assert valid[0]["type"] == "expense"


def test_valid_income_row():
    df = _df([{"date": "2026-05-01", "type": "income", "amount": "3000", "category": "Salary"}])
    valid, errors = validate_rows(df)
    assert len(valid) == 1
    assert valid[0]["category"] == "Salary"


def test_multiple_rows_mixed():
    df = _df([
        {"date": "2026-06-01", "type": "expense", "amount": "25.00"},
        {"date": "not-a-date",  "type": "expense", "amount": "10.00"},
    ])
    valid, errors = validate_rows(df)
    assert len(valid) == 1
    assert len(errors) == 1


# ── Type normalisation ────────────────────────────────────────────────────────

def test_type_case_insensitive():
    df = _df([{"date": "2026-06-01", "type": "EXPENSE", "amount": "10"}])
    valid, _ = validate_rows(df)
    assert valid[0]["type"] == "expense"


def test_type_credit_maps_to_income():
    df = _df([{"date": "2026-06-01", "type": "credit", "amount": "100"}])
    valid, _ = validate_rows(df)
    assert valid[0]["type"] == "income"


def test_type_debit_maps_to_expense():
    df = _df([{"date": "2026-06-01", "type": "debit", "amount": "20"}])
    valid, _ = validate_rows(df)
    assert valid[0]["type"] == "expense"


# ── Amount validation ─────────────────────────────────────────────────────────

def test_negative_amount_rejected():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "-10"}])
    _, errors = validate_rows(df)
    assert errors and "positive" in errors[0]["error_reason"]


def test_zero_amount_rejected():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "0"}])
    _, errors = validate_rows(df)
    assert errors


def test_amount_with_comma_separator():
    df = _df([{"date": "2026-06-01", "type": "income", "amount": "1,500.00"}])
    valid, _ = validate_rows(df)
    assert valid[0]["amount"] == 1500.0


def test_amount_too_large_rejected():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "10000000"}])
    _, errors = validate_rows(df)
    assert errors


# ── Date validation ───────────────────────────────────────────────────────────

def test_invalid_date_rejected():
    df = _df([{"date": "not-a-date", "type": "expense", "amount": "50"}])
    _, errors = validate_rows(df)
    assert errors and "date" in errors[0]["error_reason"].lower()


def test_future_date_rejected():
    df = _df([{"date": "2099-01-01", "type": "expense", "amount": "50"}])
    _, errors = validate_rows(df)
    assert errors and "future" in errors[0]["error_reason"].lower()


# ── Category defaults ─────────────────────────────────────────────────────────

def test_unknown_category_defaults_for_expense():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "10", "category": "Misc"}])
    valid, _ = validate_rows(df)
    assert valid[0]["category"] == "Other Expense"


def test_unknown_category_defaults_for_income():
    # "Bonus" is now a valid income category — use a truly unknown one
    df = _df([{"date": "2026-06-01", "type": "income", "amount": "500", "category": "Lottery Win"}])
    valid, _ = validate_rows(df)
    assert valid[0]["category"] == "Other Income"


def test_missing_category_defaults():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "10"}])
    valid, _ = validate_rows(df)
    assert valid[0]["category"] == "Other Expense"


# ── Description sanitisation ──────────────────────────────────────────────────

def test_html_stripped_from_description():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "10",
               "description": "<script>alert('xss')</script>Lunch"}])
    valid, _ = validate_rows(df)
    assert "<script>" not in valid[0]["description"]
    assert "Lunch" in valid[0]["description"]


def test_description_truncated_at_200_chars():
    df = _df([{"date": "2026-06-01", "type": "expense", "amount": "10",
               "description": "x" * 300}])
    valid, _ = validate_rows(df)
    assert len(valid[0]["description"]) == 200


# ── Error report structure ────────────────────────────────────────────────────

def test_error_row_has_row_number():
    df = _df([{"date": "bad", "type": "expense", "amount": "10"}])
    _, errors = validate_rows(df)
    assert "row_number" in errors[0]
    assert errors[0]["row_number"] == 2  # header=1, first data row=2


def test_source_field_propagated():
    df = _df([{"date": "2026-06-01", "type": "income", "amount": "100"}])
    valid, _ = validate_rows(df, source="excel_upload")
    assert valid[0]["source"] == "excel_upload"
