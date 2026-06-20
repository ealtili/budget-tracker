# 💰 Budget Tracker

A secure, multi-user personal finance tracker built with Python, Streamlit, and Docker.
Each user's data is fully isolated and encrypted at rest. Designed as an MVP with
production-grade security from the start.

---

## Features

### Finance
- **3 dashboards** — Overview (income vs expenses, net savings), Expenses (category breakdown, daily trend), Income (source breakdown, daily trend)
- **Add transactions** — unified category picker with emoji-prefixed grouping (`💰` income / `💸` expense); type auto-derived from category; editable time field pre-filled with current system time
- **Bulk import** — 5-phase CSV/Excel wizard: auto-detects column aliases, manual mapping UI for unrecognised headers, row-level validation with downloadable error report
- **9 income categories** — Salary, Freelance, Business Income, Investment Returns, Rental Income, Family & Gifts, Government & Benefits, Bonus, Other Income
- **10 expense categories** — Housing, Food & Drink, Transport, Healthcare, Entertainment, Shopping, Education, Travel, Utilities, Other Expense
- **Data export** — download your transactions as a clean CSV from Settings

### Security
- **Fernet encryption at rest** — every user's transaction file is AES-128-CBC encrypted; key supplied via `APP_SECRET_KEY` env var, never hardcoded
- **HMAC-SHA256 integrity** — second tamper-detection layer inside each encrypted file
- **bcrypt passwords** — cost factor 12; constant-time comparison; plain text never stored or logged
- **Path traversal prevention** — UUID4 regex whitelist + `Path.relative_to()` guard; no raw string path construction
- **Brute-force lockout** — 5 failed attempts → 5-min lock; each further failure → 30-min lock
- **Secure session** — `st.session_state` cleared fully on logout; sensitive fields never stored in session
- **Hardened Docker** — non-root user (`appuser`, UID 1000), read-only container FS, tmpfs `/tmp`, `HOME=/tmp`

### Admin
- **Admin panel** — designate any registered user as admin via `ADMIN_USERNAME` env var
- **User management** — view all users, reset passwords (12-char temp password shown once), delete accounts
- **Forced reset flow** — admin-reset users must set a new password before accessing the app
- Admin sees no transaction data

### UI
- **Dark / Light / System** theme switcher — CSS injection over `base = "dark"` Streamlit theme; System mode uses `@media (prefers-color-scheme)`
- **Toolbar hidden** — Streamlit's deploy/rerun/record toolbar suppressed in production

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Streamlit 1.58 |
| Package manager | uv |
| Encryption | `cryptography` (Fernet) |
| Auth | `bcrypt` |
| Data | pandas, openpyxl |
| Charts | Plotly |
| Containerisation | Docker (multi-stage build) |
| Storage | Local JSON (encrypted) |

---

## Quick Start

### Docker (recommended)

**1. Generate an encryption key**
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

**2. Create `.env`**
```env
APP_SECRET_KEY=<your-generated-key>
ADMIN_USERNAME=          # optional — set to a registered username to enable admin panel
```

**3. Run**
```bash
docker compose up --build
```

App is available at **http://localhost:8501**

> Data is stored in `./data/` on the host and survives container restarts.

---

### Local Development

**Prerequisites:** Python 3.12, [uv](https://docs.astral.sh/uv/)

```bash
# Install dependencies
uv sync --extra dev

# Set the encryption key
export APP_SECRET_KEY=<your-generated-key>   # Windows: $env:APP_SECRET_KEY="..."

# Run
uv run streamlit run src/budget_tracker/app.py
```

---

## Admin Panel

1. Register an account through the normal UI
2. Add `ADMIN_USERNAME=<your_username>` to `.env`
3. `docker compose restart` (no rebuild needed)
4. Log in — the account now shows **👑 Admin Panel** instead of the finance pages

**Emergency password reset** (if locked out):
```bash
uv run python -c "
import json, bcrypt
from pathlib import Path
f = Path('data/users.json')
data = json.loads(f.read_text())
user = next(u for u in data['users'] if u['username'] == 'YOUR_USERNAME')
user['hashed_password'] = bcrypt.hashpw(b'NEW_PASSWORD', bcrypt.gensalt(rounds=12)).decode()
user['password_reset_required'] = False
f.write_text(json.dumps(data, indent=2))
print('Done')
"
```

---

## CSV / Excel Import

Supported column names are auto-detected from common aliases. A downloadable template is available on the Upload page.

| Column | Required | Notes |
|---|---|---|
| `date` | Yes | `YYYY-MM-DD` or most date formats |
| `time` | No | `HH:MM:SS` — defaults to `00:00:00` if absent |
| `type` | Yes | `income` / `expense` — also accepts `credit` / `debit` |
| `amount` | Yes | Positive number; comma separators accepted |
| `category` | No | Fixed enum — defaults to Other if unrecognised |
| `description` | No | Free text, max 200 chars |
| `currency` | No | ISO 4217, defaults to `USD` |

**Sample files** in `sample_data/`:

| File | Description |
|---|---|
| `sample_v3_correct.csv` | 22 valid rows, all categories, time column |
| `sample_v3_mixed.xlsx` | 16 valid + 7 error rows, alias columns |
| `sample_v3_no_time.csv` | 15 valid rows, no time column (tests default) |
| `sample_aliases_mixed_v2.xlsx` | Alias columns, highlighted error rows |
| `sample_bank_statement_v2.csv` | UK bank statement format — triggers full mapping UI |
| `sample_incompatible.csv` | E-commerce format — no columns match |

---

## Running Tests

```bash
uv run pytest tests/ -v --cov=src/budget_tracker
```

44 tests covering path sanitisation, encryption round-trips, HMAC tamper detection, column alias detection, and row-level validation.

---

## Project Structure

```
budget-tracker/
├── src/budget_tracker/
│   ├── app.py                  # entry point + page router
│   ├── config.py               # data directory paths
│   ├── auth/auth_service.py    # login, register, bcrypt, admin API
│   ├── storage/
│   │   ├── paths.py            # safe_path() — path traversal guard
│   │   ├── crypto.py           # Fernet encrypt/decrypt + HMAC
│   │   └── transaction_store.py
│   ├── ingestion/
│   │   ├── categories.py       # income + expense category enums
│   │   ├── parser.py           # CSV/Excel parse + alias detection
│   │   ├── validator.py        # row-level validation
│   │   └── templates.py        # downloadable CSV template
│   └── ui/
│       ├── theme.py            # Dark/Light/System CSS injection
│       ├── login_page.py
│       ├── dashboard_page.py
│       ├── expenses_page.py
│       ├── income_page.py
│       ├── add_transaction_page.py
│       ├── upload_page.py
│       ├── settings_page.py
│       └── admin_page.py
├── tests/                      # 44 pytest unit tests
├── sample_data/                # 9 test upload files
├── data/                       # runtime data (gitignored)
│   ├── users.json              # hashed credentials
│   └── transactions/           # encrypted per-user files
├── Dockerfile                  # multi-stage: uv builder → slim runtime
├── docker-compose.yml
├── pyproject.toml
├── app_spec.md                 # full architecture specification (v5)
└── initialprompt.md            # original project brief
```

---

## Security Notes

- **Never commit `.env`** — it is gitignored. Rotate `APP_SECRET_KEY` if it is ever exposed; all existing transaction files will become unreadable (re-encryption required).
- Transaction files in `data/transactions/` are encrypted but `data/users.json` contains bcrypt hashes — treat the `data/` directory as sensitive.
- The container runs as `appuser` (UID 1000) with a read-only root filesystem. Only `./data` (bind-mounted volume) and `/tmp` (tmpfs) are writable.

---

## License

MIT
