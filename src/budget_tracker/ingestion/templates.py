import csv
import io

TEMPLATE_ROWS = [
    {
        "date": "2026-06-15",
        "time": "08:30:00",
        "type": "expense",
        "amount": "42.50",
        "category": "Food & Drink",
        "description": "Lunch at café",
        "currency": "USD",
    },
    {
        "date": "2026-06-01",
        "time": "09:00:00",
        "type": "income",
        "amount": "3000.00",
        "category": "Salary",
        "description": "June salary",
        "currency": "USD",
    },
    {
        "date": "2026-06-10",
        "time": "11:15:00",
        "type": "expense",
        "amount": "120.00",
        "category": "Utilities",
        "description": "Electricity bill",
        "currency": "USD",
    },
]

EXPECTED_COLUMNS = [
    ("date",        "Yes", "YYYY-MM-DD or most date formats"),
    ("time",        "No",  "HH:MM:SS — auto-set to 00:00:00 if missing"),
    ("type",        "Yes", "income or expense (case-insensitive)"),
    ("amount",      "Yes", "Positive number e.g. 42.50"),
    ("category",    "No",  "See category list — defaults to Other if missing or unrecognised"),
    ("description", "No",  "Free text, max 200 chars"),
    ("currency",    "No",  "ISO 4217 code e.g. USD (defaults to USD)"),
]


def generate_template_csv() -> bytes:
    buf = io.StringIO()
    fieldnames = list(TEMPLATE_ROWS[0].keys())
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(TEMPLATE_ROWS)
    return buf.getvalue().encode("utf-8")
