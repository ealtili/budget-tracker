# Budget Tracker MVP — Application Specification (v4)

> Last updated: 2026-06-20. Reflects the fully built and running application.

---

## 1. Project Goals

A secure, multi-user personal finance tracker. Each user can log in, manually add or
bulk-import income/expense transactions, and view interactive dashboards showing net
savings, category breakdowns, and monthly summaries. All user data is strictly isolated
and encrypted at rest. An admin panel allows user management without exposing any
transaction data.

---

## 2. Directory Structure

```
budget-tracker/
├── app_spec.md
├── pyproject.toml
├── uv.lock
├── Dockerfile
├── docker-compose.yml
├── .dockerignore
├── .gitignore
├── .env                          # never committed — APP_SECRET_KEY + ADMIN_USERNAME
├── .env.example                  # committed safe template
│
├── .streamlit/
│   └── config.toml               # headless, maxUploadSize, toolbarMode, dark base theme
│
├── data/                         # bind-mounted Docker volume
│   ├── users.json                # hashed credentials, lockout state, reset flags
│   └── transactions/
│       └── <uuid4>.json.enc      # Fernet-encrypted per-user transaction store
│
├── sample_data/                  # test upload files (not deployed)
│   ├── sample_correct.csv
│   ├── sample_needs_review.xlsx
│   ├── sample_incompatible.csv
│   ├── sample_correct_v2.csv     # includes time column, all income categories
│   ├── sample_aliases_mixed_v2.xlsx
│   └── sample_bank_statement_v2.csv
│
├── src/
│   └── budget_tracker/
│       ├── __init__.py
│       ├── app.py                # entry point, page router, theme injection
│       ├── config.py             # DATA_DIR / TRANSACTIONS_DIR / USERS_FILE paths
│       │
│       ├── auth/
│       │   ├── __init__.py
│       │   └── auth_service.py   # register, login, bcrypt, lockout, admin API
│       │
│       ├── storage/
│       │   ├── __init__.py
│       │   ├── paths.py          # safe_path() — UUID4 + resolve guard
│       │   ├── crypto.py         # Fernet encrypt/decrypt + HMAC-SHA256 integrity
│       │   └── transaction_store.py  # CRUD; always calls crypto on read/write
│       │
│       ├── ingestion/
│       │   ├── __init__.py
│       │   ├── categories.py     # INCOME_CATEGORIES, EXPENSE_CATEGORIES enums
│       │   ├── parser.py         # CSV/Excel parse + column alias auto-detection
│       │   ├── validator.py      # row-level validation, time parsing, error collection
│       │   └── templates.py      # downloadable CSV template generator
│       │
│       └── ui/
│           ├── __init__.py
│           ├── theme.py          # Dark/Light/System CSS injection
│           ├── login_page.py     # login, register, forced-password-change screen
│           ├── dashboard_page.py # overview KPIs + charts + transaction table
│           ├── expenses_page.py  # expenses-only dashboard
│           ├── income_page.py    # income-only dashboard
│           ├── add_transaction_page.py
│           ├── upload_page.py    # 5-phase CSV/Excel import wizard
│           ├── settings_page.py  # password change, data export, delete account
│           └── admin_page.py     # user management (admin only)
│
└── tests/
    ├── __init__.py
    ├── test_paths.py
    ├── test_crypto.py
    ├── test_auth.py
    ├── test_parser.py
    └── test_validator.py
```

---

## 3. Data Schemas

### 3a. `data/users.json`

```json
{
  "users": [
    {
      "user_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
      "username": "alice",
      "hashed_password": "$2b$12$...",
      "display_name": "Alice",
      "created_at": "2026-06-20T10:00:00Z",
      "failed_login_attempts": 0,
      "locked_until": null,
      "password_reset_required": false
    }
  ]
}
```

| Field                     | Type        | Notes                                                          |
|---------------------------|-------------|----------------------------------------------------------------|
| `user_id`                 | string      | UUID4 — file-path partition key. Never the username.           |
| `username`                | string      | Unique, lowercase-normalised, `^[a-z0-9_\-]{3,32}$`.          |
| `hashed_password`         | string      | bcrypt cost-12. Plain text never persisted.                    |
| `display_name`            | string      | Friendly UI label, max 50 chars.                               |
| `created_at`              | string      | `YYYY-MM-DDTHH:MM:SSZ` — no microseconds.                      |
| `failed_login_attempts`   | integer     | Reset to 0 on successful login.                                |
| `locked_until`            | string/null | ISO-8601 UTC; null = not locked.                               |
| `password_reset_required` | boolean     | Set by admin reset. User must change password on next login.   |

### 3b. `data/transactions/<uuid4>.json.enc`

Fernet-encrypted. Decrypted payload:

```json
{
  "version": 1,
  "hmac": "<HMAC-SHA256 hex of canonical transactions JSON>",
  "transactions": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "type": "expense",
      "amount": 42.50,
      "currency": "USD",
      "category": "Food & Drink",
      "description": "Lunch at café",
      "date": "2026-06-15",
      "time": "13:30:00",
      "created_at": "2026-06-15T13:30:00Z",
      "source": "manual"
    }
  ]
}
```

| Field         | Type   | Allowed values / constraints                                       |
|---------------|--------|--------------------------------------------------------------------|
| `version`     | int    | Schema version; currently 1.                                       |
| `hmac`        | string | HMAC-SHA256 of `json.dumps(transactions, sort_keys=True)`. Verified on read. |
| `id`          | string | UUID4, generated at write time.                                    |
| `type`        | string | `"income"` \| `"expense"`                                          |
| `amount`      | number | Positive float ≤ 9 999 999.99, rounded to 2 dp.                    |
| `currency`    | string | ISO 4217, default `"USD"`.                                         |
| `category`    | string | Fixed enum — see §6.                                               |
| `description` | string | Optional; HTML-stripped; max 200 chars.                            |
| `date`        | string | `YYYY-MM-DD` — used for date filtering.                            |
| `time`        | string | `HH:MM:SS` — auto-set from system clock (manual) or parsed from data (upload). Defaults to `00:00:00` if unavailable. |
| `created_at`  | string | `YYYY-MM-DDTHH:MM:SSZ` — record creation timestamp, no microseconds. |
| `source`      | string | `"manual"` \| `"csv_upload"` \| `"excel_upload"`                   |

---

## 4. Security Design

### 4a. Password Hashing

- Library: **`bcrypt`** (cost factor **12**)
- `bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12))`
- Verification: `bcrypt.checkpw(plain.encode("utf-8"), stored_hash)` — constant-time
- A module-level `_DUMMY_HASH` is used for constant-time comparison when the username
  does not exist, preventing timing-based user enumeration
- Plain-text passwords are never logged, stored, or placed in `st.session_state`

### 4b. Brute-Force / Account Lockout

| Attempts | Action |
|----------|--------|
| 1–4      | Increment counter, no lockout |
| 5        | Lock for 5 minutes |
| 6+       | Lock for 30 minutes per additional failure |

- Successful login resets `failed_login_attempts = 0` and `locked_until = null`
- Login always returns `"Invalid username or password"` — lockout state is never disclosed

### 4c. Path Traversal Prevention (`storage/paths.py`)

`safe_path(user_id)` is the single gatekeeper for all user-scoped file paths:

1. **UUID4 regex** — whitelist that structurally rejects `../`, null bytes, whitespace,
   encoded traversal sequences before any filesystem access
2. **`Path.resolve()` + `relative_to()`** — second-layer defence against symlink-based
   traversal; raises `ValueError` if resolved path escapes `TRANSACTIONS_DIR`

All storage functions call `safe_path()` — no raw string path construction anywhere.

### 4d. Encryption at Rest (`storage/crypto.py`)

Every `<uuid4>.json.enc` file is encrypted with **Fernet** (AES-128-CBC + HMAC-SHA256):

```
APP_SECRET_KEY env var (base64url, 32 bytes)
  → Fernet(key).encrypt(json_bytes) → .json.enc
  → Fernet(key).decrypt(.json.enc) → json_bytes   [raises InvalidToken on tamper]
```

- Key provided exclusively via `APP_SECRET_KEY` environment variable
- App refuses to start if the variable is absent or malformed
- Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

### 4e. HMAC Integrity (tamper detection)

A second HMAC-SHA256 digest over the `transactions` array is stored inside the JSON
envelope. Verified on every read using `hmac.compare_digest` (constant-time). Detects
out-of-band file edits that survive Fernet decryption (e.g., key reuse attacks).

### 4f. File Permissions

`os.chmod(path, 0o600)` applied after every write — owner read/write only. Silently
ignored on Windows during local development; enforced inside the Linux container.

### 4g. Input Sanitisation

| Field         | Rule |
|---------------|------|
| `username`    | Lowercase; must match `^[a-z0-9_\-]{3,32}$` |
| `password`    | Minimum 8 characters |
| `description` | Strip HTML tags; truncate to 200 chars |
| `amount`      | Coerce to float; reject ≤ 0 or > 9 999 999 |
| `date`        | Parse via `dateutil`; reject future dates |
| `time`        | Parse to `HH:MM:SS`; default `"00:00:00"` on failure |
| `category`    | Must be in fixed enum; reject otherwise |
| `type`        | Normalise to `"income"` or `"expense"`; reject anything else |

### 4h. Session Management

| Event                      | Action |
|----------------------------|--------|
| Login success              | Set `authenticated`, `user_id`, `username`, `display_name` in session state |
| `password_reset_required`  | Set `must_change_password = True`; block app until new password is set |
| Every protected page       | `if not st.session_state.get("authenticated"): st.stop()` |
| Logout                     | `st.session_state.clear()` → `st.rerun()` |
| Never stored in session    | Raw password, bcrypt hash, Fernet key |

### 4i. Admin Security

- Admin designation is via `ADMIN_USERNAME` environment variable only — no special
  registration flow, no admin flag in `users.json`
- Admin navigation shows **only** user management and own settings — no transaction data
- `admin_list_users()` returns a projected view: no `hashed_password`, no `user_id`
  (except for internal operations), no transaction counts
- Admin cannot delete their own account
- Temporary passwords generated with `secrets.choice` (cryptographically secure PRNG),
  12 characters, alphanumeric; shown to admin once and never stored in plain text

---

## 5. CSV / Excel Import Pipeline (5 Phases)

### 5a. Expected Column Schema

| Column        | Required | Format / values |
|---------------|----------|-----------------|
| `date`        | Yes      | `YYYY-MM-DD` or most common date formats |
| `time`        | No       | `HH:MM:SS` — defaults to `00:00:00` if absent |
| `type`        | Yes      | `income` or `expense` (case-insensitive; `credit`/`debit` also accepted) |
| `amount`      | Yes      | Positive number, e.g. `42.50`; comma separators accepted |
| `category`    | No       | Fixed enum (see §6); unrecognised → `Other Income` / `Other Expense` |
| `description` | No       | Free text, max 200 chars |
| `currency`    | No       | ISO 4217 code; defaults to `USD` |

Downloadable CSV template (with example rows) available on the Upload page.

### 5b. Column Alias Dictionary

| Canonical     | Recognised aliases |
|---------------|--------------------|
| `date`        | `date`, `transaction date`, `txn date`, `trans date`, `value date`, `posting date`, `when` |
| `time`        | `time`, `transaction time`, `txn time`, `hour`, `timestamp`, `hh mm ss` |
| `type`        | `type`, `transaction type`, `txn type`, `direction`, `flow`, `debit credit`, `dr cr` |
| `amount`      | `amount`, `amt`, `sum`, `value`, `price`, `cost`, `debit`, `credit`, `transaction amount` |
| `category`    | `category`, `cat`, `label`, `tag`, `group`, `merchant category`, `expense type` |
| `description` | `description`, `desc`, `memo`, `notes`, `note`, `details`, `narrative`, `particulars`, `reference` |
| `currency`    | `currency`, `ccy`, `curr`, `iso currency`, `currency code` |

### 5c. Import Pipeline

```
Phase 0 — Instructions & Template
  Show expected column table + downloadable CSV template
  File uploader (.csv / .xlsx, max 10 MB)

Phase 1 — Parse & Auto-Detect
  Read into pandas DataFrame
  Normalise headers (lowercase, collapse non-alphanumeric to spaces)
  Match against alias dictionary → auto_mapping

Phase 2 — Column Mapping  [only if any canonical column unresolved]
  Dropdown per unresolved column: user maps to a df column or skips
  Required columns (date, type, amount) must be mapped to proceed

Phase 3 — Row Validation  [triggered by Validate button]
  Apply mapping; validate every row (§4g rules)
  Collect valid_rows[] and error_rows[] with per-row error reasons

Phase 4 — Review & Decision
  Metrics: N valid rows / M rows with issues
  Expandable table of invalid rows with error details
  [Download error report (.csv)]  [Import N valid rows]  [Cancel]

Phase 5 — Write
  Append valid rows to encrypted store
  Show success toast; clear import session state
```

### 5d. Error Report

CSV columns: `row_number`, `raw_date`, `raw_amount`, `raw_type`, `raw_category`,
`raw_description`, `error_reason`.

---

## 6. Transaction Categories

### Income (9 categories)

`Salary` · `Freelance` · `Business Income` · `Investment Returns` · `Rental Income` ·
`Family & Gifts` · `Government & Benefits` · `Bonus` · `Other Income`

### Expense (10 categories)

`Housing` · `Food & Drink` · `Transport` · `Healthcare` · `Entertainment` ·
`Shopping` · `Education` · `Travel` · `Utilities` · `Other Expense`

---

## 7. UI Flow & Page Structure

### Unauthenticated

```
App load → authenticated = False
  → Login page (full screen, no sidebar)
        ├── Login tab   → bcrypt verify → set session → st.rerun()
        └── Register tab → create user → auto-login → st.rerun()

Post-login, if password_reset_required = True:
  → Forced Change Password screen (cannot access app until complete)
  → set_new_password() clears flag → st.rerun() → main app
```

### Regular User Navigation (sidebar)

| Page | Description |
|------|-------------|
| 📊 Overview | KPI row + donut + monthly bar + filterable transaction table |
| 💸 Expenses | Expenses-only KPIs, horizontal bar by category, donut, daily trend, table |
| 💰 Income | Income-only KPIs, bar by source, donut, daily trend, table |
| ➕ Add Transaction | Manual entry form; category drives type; editable time field |
| 📂 Upload | 5-phase CSV/Excel import wizard |
| ⚙️ Settings | Appearance (theme), change password, export CSV, delete account |

Sidebar also shows: 🎨 Theme selector (System / Light / Dark), 🚪 Logout button.

### Admin Navigation (sidebar)

Admin accounts (username matches `ADMIN_USERNAME` env var) see a different navigation:

| Page | Description |
|------|-------------|
| 👑 Admin Panel | User list, reset passwords, delete users, change own password |
| ⚙️ Settings | Appearance, change own password |

Admin **cannot** access any transaction dashboards or user data.

### Overview Dashboard

```
┌────────────────────────────────────────────────────────┐
│  Date range selector (default: current month)           │
├────────────────┬────────────────┬───────────────────────┤
│  Total Income  │ Total Expenses │  Net Savings (±delta)  │
├────────────────┴────────────────┴───────────────────────┤
│  Spending by Category (Plotly donut)                    │
├─────────────────────────────────────────────────────────┤
│  Monthly Income vs Expenses (Plotly grouped bar)        │
├─────────────────────────────────────────────────────────┤
│  Transactions table (search + type filter, sortable)    │
│  Date | Time | Type | Category | Description | Amount   │
└─────────────────────────────────────────────────────────┘
```

### Add Transaction Form

**Category picker lives outside the form** so switching it immediately reruns the page
and updates the type badge — Streamlit forms batch widget interactions until submit,
which would otherwise prevent the category list from updating.

| Field       | Widget            | Notes |
|-------------|-------------------|-------|
| Category    | `st.selectbox`    | All 19 categories in one list; `💰` prefix = income source, `💸` prefix = expense. Placed **outside** the form. |
| Type badge  | `st.success` / `st.error` | Auto-derived from selected category — no manual radio button needed |
| Amount      | `st.number_input` | > 0, step 0.01, max 9 999 999 |
| Date        | `st.date_input`   | ≤ today |
| Time        | `st.text_input`   | `HH:MM:SS` format; pre-filled with current system time; user can edit for past transactions. Validated with `datetime.strptime` on submit. (`st.time_input` not used — it enforces a 60-second minimum step, preventing second-level precision.) |
| Description | `st.text_input`   | Optional, max 200 chars |

### Settings Page

- **Appearance** — Theme selector (System / Light / Dark)
- **Change Password** — Requires current password; updates bcrypt hash
- **Download My Data** — Decrypted transactions as CSV
- **Delete Account** — Username re-entry confirmation; removes user record and `.json.enc`

### Admin Panel

- Summary metrics: total users / locked accounts / pending resets
- Per-user accordion: username, display name, registration date, failed login count,
  lock status, reset-pending indicator
- Actions per user: **Reset Password** (generates 12-char temp password, shown once) /
  **Delete User** (two-click confirmation; also deletes transaction file)
- **Change Admin Password** section at bottom

---

## 8. Theming

Runtime theme switching via CSS injection in `ui/theme.py`.

| Mode   | Mechanism |
|--------|-----------|
| Dark   | Palette reinforcement CSS injected over `base = "dark"` (default) |
| Light  | Full surface-flip CSS (white backgrounds, dark text) over dark base |
| System | Dark rules unconditionally + `@media (prefers-color-scheme: light)` applies light rules |

`config.toml` uses `base = "dark"` so Streamlit's JS bridge propagates dark colours to
canvas-rendered components (Glide Data Grid dataframe, tooltips, dropdowns) without CSS.
Our CSS only targets HTML-rendered surfaces — no overrides on `.dvn-scroller` or canvas
internals (those break the canvas renderer).

Preference is stored in `st.session_state["app_theme"]` (resets on logout).

---

## 9. Dependencies

```toml
[project]
name = "budget-tracker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "streamlit>=1.35",
    "bcrypt>=4.1",
    "cryptography>=42.0",
    "pandas>=2.2",
    "openpyxl>=3.1",
    "plotly>=5.22",
    "python-dateutil>=2.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.0", "pytest-cov>=5.0"]
```

---

## 10. Docker Design

### Multi-Stage Build

| Stage   | Base image | Purpose |
|---------|------------|---------|
| builder | `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` | Install deps into `.venv` via uv |
| runtime | `python:3.12-slim-bookworm` | Copy `.venv` + `src/` only; no build tools |

Key optimisations:
- Two-step `uv sync`: dependencies in one layer, project source in the next — code changes don't re-download packages
- `--mount=type=cache,target=/root/.cache/uv` — BuildKit cache across rebuilds
- `UV_COMPILE_BYTECODE=1` — pre-compile `.pyc` for faster cold start
- Final image: ~150 MB (vs ~500 MB naive single-stage)

### Security Hardening

| Measure | Detail |
|---------|--------|
| Non-root user | `appuser` (UID 1000), `--no-create-home --home-dir /tmp` |
| `HOME=/tmp` | Redirects all `~` expansions (Streamlit cache, Python internals) to writable tmpfs |
| `read_only: true` | Container root FS is immutable at runtime |
| `tmpfs: /tmp` | 64 MB writable scratch for Streamlit/uvicorn |
| `VOLUME /app/data` | Only the data volume is writable and persistent |
| `toolbarMode = minimal` | Hides Streamlit's deploy/rerun/record toolbar in production |

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `APP_SECRET_KEY` | Yes | Fernet encryption key. Generate once, store in `.env`. |
| `ADMIN_USERNAME` | No | Username to grant admin panel access. Must be a registered user. |
| `BUDGET_DATA_DIR` | No | Override data directory path (default: `./data`; Docker: `/app/data`). |

### `docker-compose.yml` Summary

```yaml
services:
  budget-tracker:
    build: .
    ports: ["8501:8501"]
    volumes: ["./data:/app/data"]
    environment:
      APP_SECRET_KEY: ${APP_SECRET_KEY}
      ADMIN_USERNAME: ${ADMIN_USERNAME:-}
    env_file: [{path: .env, required: false}]
    restart: unless-stopped
    read_only: true
    tmpfs: [/tmp:size=64m]
```

### `.streamlit/config.toml`

```toml
[server]
headless = true
maxUploadSize = 10        # MB

[client]
toolbarMode = "minimal"   # hides Deploy / Rerun / Record toolbar

[theme]
base = "dark"
primaryColor      = "#4CAF50"
backgroundColor   = "#0e1117"
secondaryBackgroundColor = "#161b22"
textColor         = "#e6edf3"
```

---

## 11. Setting Up Admin Access

1. Register an account through the normal registration UI
2. Add `ADMIN_USERNAME=<your_username>` to `.env`
3. Run `docker compose restart` (no rebuild needed — env var is read at runtime)
4. Log in — the account now sees the Admin Panel instead of the finance pages

To reset the admin password without logging in (e.g., forgotten):
```bash
uv run python -c "
import json, bcrypt
from pathlib import Path
f = Path('data/users.json')
data = json.loads(f.read_text())
user = next(u for u in data['users'] if u['username'] == 'YOURUSERNAME')
user['hashed_password'] = bcrypt.hashpw(b'NEWPASSWORD', bcrypt.gensalt(rounds=12)).decode()
user['password_reset_required'] = False
f.write_text(json.dumps(data, indent=2))
print('Done')
"
```

---

## 12. Sample Data Files

Located in `sample_data/`:

| File | Purpose |
|------|---------|
| `sample_correct.csv` | 19 rows, canonical columns, all valid |
| `sample_needs_review.xlsx` | 14 valid + 6 error rows; alias column names; highlighted red |
| `sample_incompatible.csv` | E-commerce format — no columns match schema |
| `sample_correct_v2.csv` | 22 rows, includes `time` column, all 9 income categories used |
| `sample_aliases_mixed_v2.xlsx` | 15 valid + 6 errors; alias columns + time column |
| `sample_bank_statement_v2.csv` | UK bank statement (Value Date, Debit, Credit, Balance) — triggers full column mapping UI |
| `sample_v3_correct.csv` | 22 rows; all 9 income + 10 expense categories covered; full time column; all valid |
| `sample_v3_mixed.xlsx` | 16 valid + 7 error rows (one per error type); alias columns (`Txn Date`, `Direction`, `Amt`, `Label`); time column; highlighted red |
| `sample_v3_no_time.csv` | 15 valid rows; **no time column** — verifies `00:00:00` default is applied; alias column names (`Transaction Date`, `Merchant Category`, `ISO Currency`) |

---

## 13. Verification Checklist

| # | Test | Pass condition |
|---|------|----------------|
| 1 | `docker compose up --build` | App at `http://localhost:8501` |
| 2 | Register two users; add transactions for each | Users see only their own data |
| 3 | Inspect `data/transactions/*.json.enc` | Binary — not human-readable |
| 4 | `safe_path("../../etc/passwd")` unit test | `ValueError` raised |
| 5 | Corrupt a `.json.enc` file; reload dashboard | Generic error, no data leaked |
| 6 | Upload `sample_correct_v2.csv` | 22 rows imported, time column visible |
| 7 | Upload `sample_aliases_mixed_v2.xlsx` | Auto-detect columns; 15 imported; error report for 6 |
| 8 | Upload `sample_bank_statement_v2.csv` | Column mapping UI shown; required fields unresolved |
| 9 | 5 failed logins on an account | Account locks; generic error returned |
| 10 | Set `ADMIN_USERNAME`; log in as that user | Admin Panel visible; no transaction data shown |
| 11 | Admin resets a user's password | Temp password shown once; user forced to change on next login |
| 12 | Add transaction — select Income category (e.g. Salary) | Type badge shows Income; form submits correctly |
| 12b | Add transaction — edit time field to a past time | Saved time matches edited value, not system time |
| 12c | Add transaction — enter invalid time (e.g. `99:99`) | Validation error shown; transaction not saved |
| 13 | Switch theme to Light / Dark / System | Surfaces update; dataframes remain readable |
| 14 | `pytest tests/ --cov=src` | 44 tests pass |
| 15 | `docker exec <container> whoami` | `appuser` |
| 16 | `docker inspect <container> --format='{{.HostConfig.ReadonlyRootfs}}'` | `true` |
