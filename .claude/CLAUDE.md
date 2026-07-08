# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**All development runs in Docker** — the app is built and exercised via the container, not a local `uv run streamlit`. `docker compose up --build -d` is the primary loop for verifying a change.

```bash
# Generate a Fernet encryption key, then put it in .env as APP_SECRET_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Build and run the app (APP_SECRET_KEY must be set in .env first)
docker compose up --build -d

# Pick up ADMIN_USERNAME / other .env changes without rebuilding
docker compose restart

# Tear down
docker compose down

# Tail logs
docker compose logs -f
```

**Testing:** `uv sync --extra dev` + `uv run pytest` locally is currently the only way to run the test suite — the shipped `Dockerfile` builds a production-only image (`uv sync --no-dev`, and it deletes any `tests/` directories found under `.venv` for image size). Neither build stage installs pytest or copies the project's `tests/` folder, so there is no in-container equivalent today. If that's needed, it would require a dev-only build target/compose override that installs `--extra dev` and mounts or `COPY`s `tests/`.

```bash
# Local-only (no Docker path exists yet — see note above)
uv sync --extra dev
uv run pytest tests/ -v
uv run pytest tests/test_paths.py -v
uv run pytest tests/test_validator.py::test_html_stripped_from_description -v
uv run pytest tests/ --cov=src/budget_tracker --cov-report=term-missing
```

## Environment Variables

| Variable | Required | Notes |
|---|---|---|
| `APP_SECRET_KEY` | Yes | Fernet key. App refuses to start without it. |
| `ADMIN_USERNAME` | No | Grants admin panel to this registered username. Restart (not rebuild) picks it up. |
| `BUDGET_DATA_DIR` | No | Override data directory. Defaults to `./data` when run locally; Docker always uses `/app/data`, backed by the `budget_tracker_data` named volume. |

Store in `.env` (gitignored). Never hardcode.

- `APP_SECRET_KEY` change → requires rebuild (`--build`) because it's baked into the image env; all existing `.json.enc` files become unreadable.
- `ADMIN_USERNAME` change → `docker compose restart` is enough (read at runtime).

**Emergency admin password reset** (if locked out of the UI) — run inside the
container, against the volume-mounted path, not a host path:
```bash
docker compose exec budget-tracker python -c "
import json, bcrypt
from pathlib import Path
f = Path('/app/data/users.json')
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

**Important Streamlit constraint:** widgets inside `st.form` do not trigger reruns until submit. Any widget whose value needs to influence other widgets on the same render (e.g. the category picker driving the type badge in `add_transaction_page.py` and `transactions_page.py`'s edit form) must live **outside** the form.

### Transactions page (`ui/transactions_page.py`)

Full CRUD table (date range + search + type/category filters, single-row select-to-edit-or-delete), separate from the read-only tables embedded in `dashboard_page.py`/`expenses_page.py`/`income_page.py`. Two things worth knowing before touching it:

- After filtering, `disp` is always `reset_index(drop=True)` before being passed to `st.dataframe(..., selection_mode="single-row")`. Skipping this lets a stale row index from a previous (larger) filter result outlive a rerun that shrinks the table, selecting the wrong record.
- Edit/delete both re-fetch the record by `id` via `get_transactions()` rather than trusting the row already sitting in the filtered `disp` frame, since that frame can be one rerun stale.

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
| `users.json` edited directly inside the volume | Nothing — app reads it on every request |

### What must never be committed

`.env`, `graphify-out/` (both in `.gitignore`). The `.env.example` is the safe template to commit instead. `.gitignore` also still excludes `data/` as a defensive leftover, but runtime data no longer lives there in practice — it's entirely in the `budget_tracker_data` named Docker volume, outside the repo tree (see §Data files below). If a stray `./data/` shows up locally, it's leftover from before the volume migration and is safe to ignore or delete.

### Skipping the graphify hook

If a commit is in a tight loop or CI environment where you don't want the background rebuild:
```bash
GRAPHIFY_SKIP_HOOK=1 git commit -m "..."
```

---

## Data files

Runtime data lives in the named Docker volume `budget_tracker_data`, mounted at
`/app/data` in the container — **not** a `./data` directory in this repo. Access it via
`docker compose exec budget-tracker sh` or `docker run --rm -it -v budget_tracker_data:/data alpine sh`
(prefix with `MSYS_NO_PATHCONV=1` on Windows/Git Bash).

- `/app/data/users.json` — plaintext JSON (bcrypt hashes, no sensitive plaintext)
- `/app/data/transactions/<uuid4>.json.enc` — Fernet-encrypted; unreadable without `APP_SECRET_KEY`
- If `APP_SECRET_KEY` changes, all existing `.json.enc` files become unreadable
- Backup/restore via `docker run --rm -v budget_tracker_data:/data -v "$(pwd)":/backup alpine tar czf/xzf ...` (see `app_spec.md` §10 for full commands)

## Graphify Knowledge Graph

The codebase is indexed as a knowledge graph in `graphify-out/` (gitignored — regenerated locally).

**Check graph is fresh before querying:**
```bash
# Compare the commit hash in graphify-out/GRAPH_REPORT.md with HEAD
git rev-parse HEAD
```

**Rebuild after code changes (no API key needed):**
```bash
graphify update .
```

**Full rebuild including docs/specs (requires an LLM API key):**
```bash
ANTHROPIC_API_KEY=<key> graphify . --backend claude
```

**Git hooks keep the graph fresh automatically** — post-commit and post-checkout hooks run `graphify update .` in the background after every commit and branch switch. The hook skips safely during rebase/merge and is bypassed with `GRAPHIFY_SKIP_HOOK=1`.

**After a fresh clone**, the `graphify-out/` directory won't exist. Run `graphify update .` once to build the code graph locally.

**Key findings from the graph (251 nodes, 393 edges, 21 communities):**
- God nodes (most connected): `validate_rows()` (29 edges), `safe_path()` (16 edges), `encrypt_payload()` (12 edges) — changes to these ripple widest
- No import cycles detected
- Communities map cleanly to subsystems: auth, storage/crypto, paths, ingestion/parser, ingestion/validator, UI pages, theming, admin

## Tests

Tests are in `tests/`. `pytest.ini` sets `pythonpath = ["src"]` so imports work without installing. Set `BUDGET_DATA_DIR` to a temp dir in tests that touch the filesystem (see `test_paths.py` for the pattern).

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).

---

## Coding Behaviour Guidelines

Behavioral guidelines to reduce common LLM coding mistakes and ensure secure, predictable execution. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution, security, and precision over speed. For trivial, low-risk tasks, use judgment and don't over-apply.

## 1. Think Before Coding
**Reason thoroughly. Output concisely. Don't assume; don't hide confusion.**

Before implementing:
- State your assumptions and the tradeoffs that affect the user's decision before you code — and nothing more.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- Keep reasoning and planning out of the code; if a plan is worth showing, put it as brief prose before the block, not inside it.

**Ask vs. proceed (decision boundary):**
- **Proceed autonomously** when the outcome is *verifiable* and *reversible* — even if some detail is ambiguous, pick the most reasonable interpretation, state it, and move.
- **Stop and ask first** when the action is *consequential or irreversible* (data loss, schema changes, public-facing output, spend, irreversible config) **and** the intent is genuinely ambiguous.

## 2. Simplicity First
**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

The operative rule: every line must trace to a stated requirement. Speculative generality is the failure mode to avoid.

## 3. Surgical Changes
**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code or issues, mention them — don't act on them.

When your changes create orphans:
- Remove imports/variables/functions that **your** changes made unused — but only if you can reasonably confirm they aren't referenced elsewhere (including dynamic/string-based imports and reflection). When in doubt, leave them and flag for review.
- Don't remove pre-existing dead code unless explicitly asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution
**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals where a verification surface exists:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

**When tests don't apply** (config, docs, UI tweaks, exploratory work) or **no usable test suite exists**, define an alternative, explicit success check — manual reproduction steps, expected output, a lint/build/typecheck pass — and state it. Don't manufacture hollow tests, and don't assume a green suite that may not exist; if the baseline is already failing, surface that before changing anything.

For multi-step tasks, state a brief plan:
```text
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong, checkable success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Secure by Design
**Never sacrifice security for simplicity. Protect the execution environment and the supply chain.**

- Always validate and sanitize external/user inputs.
- Use parameterized queries; avoid constructing dynamic execution strings.
- Follow least privilege in all configurations, IAM roles, and file permissions.
- **Secrets:** Never hardcode credentials, keys, or tokens in source. Never commit `.env` or secret material. Never log secrets, tokens, or PII.
- **Dependencies:** Don't introduce a new dependency silently. Flag the package, its purpose, and (where one exists) a lighter or already-present alternative before adding it. Treat new third-party code as supply-chain surface.
- If a requested implementation introduces a known vulnerability or bypasses a security control (e.g., Model Context Protocol boundaries, Zero Trust policies): **flag the specific risk, require explicit acknowledgment, and offer a secure alternative.** Proceed only after the user confirms with that risk in view. Reserve outright refusal for requests whose evident purpose is to cause harm — not for legitimate security testing, deliberately vulnerable test fixtures, or red-team work.

## 6. Tool & Environment Execution Boundaries
**Read before you write. Validate before you execute.**

When operating with autonomy, using external tools, or executing commands:
- Never execute destructive commands (e.g., `rm -rf`, bulk database drops, `git push --force`, global config overwrites) without explicit user confirmation.
- Read file states and verify directory context before creating or modifying files.
- If a script or command fails, do not blindly retry — it may have already partially applied. Read the error, state the suspected cause in one or two lines, and verify current state before retrying. If the failed operation has non-idempotent or irreversible side effects and the state is uncertain, stop and ask instead of retrying.

---

**These guidelines are working if:** diffs are surgical, success criteria are explicit and checked, dependencies and secrets are handled deliberately, risky actions are confirmed rather than assumed, and clarifying questions precede consequential work rather than following mistakes.