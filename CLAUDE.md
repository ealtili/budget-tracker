# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (including dev)
uv sync --extra dev

# Run the app locally (APP_SECRET_KEY must be set first)
export APP_SECRET_KEY=<fernet-key>   # Windows: $env:APP_SECRET_KEY="..."
uv run streamlit run src/budget_tracker/app.py

# Run all tests
uv run pytest tests/ -v

# Run a single test file
uv run pytest tests/test_paths.py -v

# Run a single test by name
uv run pytest tests/test_validator.py::test_html_stripped_from_description -v

# Run tests with coverage
uv run pytest tests/ --cov=src/budget_tracker --cov-report=term-missing

# Docker — build and run
docker compose up --build -d
docker compose restart          # pick up .env changes without rebuilding
docker compose down

# Generate a Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `APP_SECRET_KEY` | Yes | Fernet key. App refuses to start without it. |
| `ADMIN_USERNAME` | No | Grants admin panel to this registered username. Restart (not rebuild) picks it up. |
| `BUDGET_DATA_DIR` | No | Override data directory. Defaults to `./data`; Docker sets it to `/app/data`. |

Store in `.env` (gitignored). Never hardcode.

- `APP_SECRET_KEY` change → requires rebuild (`--build`) because it's baked into the image env; all existing `.json.enc` files become unreadable.
- `ADMIN_USERNAME` change → `docker compose restart` is enough (read at runtime).

**Emergency admin password reset** (if locked out of the UI):
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
"
```

## Architecture

### Data flow

Every user request that reads or writes transactions follows this path:

```
UI page → transaction_store.py → safe_path() → crypto.py → .json.enc file
```

- **`config.py`** — resolves `DATA_DIR`, `TRANSACTIONS_DIR`, `USERS_FILE` from `BUDGET_DATA_DIR` env var or project root. Import these paths from here; never construct them manually.
- **`storage/paths.py`** — `safe_path(user_id)` is the only way to get a transaction file path. It enforces a strict UUID4 regex then `Path.relative_to()` to block path traversal. All storage functions call it.
- **`storage/crypto.py`** — `encrypt_payload(dict) → bytes` and `decrypt_payload(bytes) → dict`. Fernet encryption + HMAC-SHA256 integrity check on every read/write. Never read/write `.json.enc` files directly.
- **`storage/transaction_store.py`** — CRUD layer. All functions call `safe_path()` and `crypto`. The payload schema is `{version, hmac, transactions: [...]}`.

### Auth

`auth/auth_service.py` owns all user operations. Key points:

- Passwords are bcrypt (cost 12). A module-level `_DUMMY_HASH` is used when the username doesn't exist so login always takes the same time (prevents enumeration).
- Admin access is determined solely by `ADMIN_USERNAME` env var — no role field in `users.json`. `is_admin(username)` is the check used in `app.py` and `admin_page.py`.
- `password_reset_required` flag in `users.json` triggers a forced change screen. `set_new_password()` (no current-password check) is the only function that clears it.

### Streamlit page routing

`app.py` is the entry point. It runs `apply_theme()` on every render, then routes to either `_USER_PAGES` or `_ADMIN_PAGES` dict based on `is_admin()`. Each page module exposes a single `render()` function.

**Important Streamlit constraint:** widgets inside `st.form` do not trigger reruns until submit. Any widget whose value needs to influence other widgets on the same render (e.g. the category picker driving the type badge in `add_transaction_page.py`) must live **outside** the form.

### Theming

`ui/theme.py` injects CSS via `st.markdown`. `config.toml` sets `base = "dark"` so Streamlit's JS bridge propagates dark colours into canvas-rendered components (Glide Data Grid, tooltips). **Do not add CSS overrides targeting `.dvn-scroller`, `[data-testid="stDataFrameResizable"]`, or `[role="gridcell"]`** — these fight the JS renderer and make dataframe cells invisible.

### CSV/Excel import

Five-phase pipeline in `ui/upload_page.py`:
1. Instructions + file upload
2. Auto-detect column aliases (`ingestion/parser.py` → `detect_mapping()`)
3. Manual mapping UI for unresolved columns
4. Row validation (`ingestion/validator.py` → `validate_rows()`) — returns `(valid_rows, error_rows)`
5. Import confirmation + write

Column aliases are defined in `parser.COLUMN_ALIASES`. Adding a new canonical field requires updating that dict, `validator.py`, and `templates.py`.

### Categories

`ingestion/categories.py` is the single source of truth for `INCOME_CATEGORIES` and `EXPENSE_CATEGORIES`. The validator uses `.title()` to normalise incoming values before matching — all category strings must survive a `.title()` round-trip unchanged (e.g. `"Family & Gifts".title() == "Family & Gifts"` ✓).

### Timestamps

- `created_at` — always `datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")` (no microseconds)
- `time` — stored as `"HH:MM:SS"`. Manual entry: from form text input. CSV upload: parsed by `validator._parse_time()`, defaults to `"00:00:00"` if absent.
- `st.time_input` is **not used** — it enforces a 60-second minimum step, which prevents second-level precision.

## Git Workflow

### Branch strategy

- `main` is the only long-lived branch and is always deployable
- Use short-lived feature branches for any non-trivial change: `git checkout -b feat/budget-limits`
- Merge back to `main` via PR or direct push for solo work

### Commit message format

Follow conventional commits — `<type>: <subject>` (imperative, lowercase subject):

```
feat: add monthly budget limits per category
fix: category picker not updating after Income selected
docs: update app_spec.md with budget limits schema
docker: reduce image size by stripping .so debug symbols
refactor: extract date parsing into shared utility
test: add validator tests for future-date rejection
```

Common types for this project: `feat`, `fix`, `docs`, `docker`, `refactor`, `test`, `chore`

### Pre-commit checklist

1. `uv run pytest tests/ -q` — all tests pass
2. If you changed data schemas (transaction fields, user fields) → update `app_spec.md`
3. If you changed architecture, added a page, or changed a non-obvious constraint → update `CLAUDE.md`

### What requires a Docker rebuild vs restart

| Change | Action |
|---|---|
| Source code (`src/`), `Dockerfile`, `pyproject.toml`, `.streamlit/` | `docker compose up --build -d` |
| `ADMIN_USERNAME` in `.env` | `docker compose restart` |
| `APP_SECRET_KEY` in `.env` | `docker compose up --build -d` + all `.json.enc` files become unreadable |
| `data/users.json` edited directly | Nothing — app reads it on every request |

### What must never be committed

`.env`, `data/` (both in `.gitignore`). The `.env.example` is the safe template to commit instead.

---

## Data files

- `data/users.json` — plaintext JSON (bcrypt hashes, no sensitive plaintext)
- `data/transactions/<uuid4>.json.enc` — Fernet-encrypted; unreadable without `APP_SECRET_KEY`
- If `APP_SECRET_KEY` changes, all existing `.json.enc` files become unreadable

## Tests

Tests are in `tests/`. `pytest.ini` sets `pythonpath = ["src"]` so imports work without installing. Set `BUDGET_DATA_DIR` to a temp dir in tests that touch the filesystem (see `test_paths.py` for the pattern).
