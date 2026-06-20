# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

# UV tuning:
#   COMPILE_BYTECODE  – pre-compile .py → .pyc for faster cold-start
#   LINK_MODE=copy    – required when source/target are on different filesystems (Docker cache mounts)
#   PYTHON_DOWNLOADS  – never let uv fetch its own Python; use the image's interpreter
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# ── Layer 1: dependencies only (rebuilt only when pyproject.toml / uv.lock change) ──
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-install-project --no-dev

# ── Layer 2: application source (rebuilt on every code change) ──────────────
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# ── Layer 3: slim the venv before it is copied to the runtime stage ──────────
# Strip debug symbols from compiled extensions — saves ~150-200 MB from
# pyarrow, numpy, pandas, cryptography and other packages with large .so files.
# Also remove test directories and type-stub files not needed at runtime.
RUN find /app/.venv -name "*.so" -exec strip --strip-debug {} \; 2>/dev/null || true \
 && find /app/.venv -type d \( -name "tests" -o -name "test" \) \
        -not -path "*/pytest*" -exec rm -rf {} + 2>/dev/null || true \
 && find /app/.venv -name "*.pyi" -delete 2>/dev/null || true


# ── Stage 2: minimal runtime image ────────────────────────────────────────────
FROM python:3.12-slim-bookworm AS runtime

# Non-root user. Home dir is /tmp (our writable tmpfs) so any library that
# expands ~ (Streamlit metrics, Python caches, etc.) lands somewhere writable.
RUN useradd --uid 1000 --no-create-home --home-dir /tmp --shell /sbin/nologin appuser

WORKDIR /app

# Copy only the virtual environment and application source from builder
COPY --from=builder --chown=appuser:appuser /app/.venv  /app/.venv
COPY --from=builder --chown=appuser:appuser /app/src    /app/src

# Streamlit configuration (theme, upload limit)
COPY --chown=appuser:appuser .streamlit/ /app/.streamlit/

# Pre-create data directories with correct ownership
RUN mkdir -p /app/data/transactions && chown -R appuser:appuser /app/data

# Activate the venv for all subsequent commands
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    # Redirect ~ to the writable tmpfs — prevents read-only FS errors from
    # Streamlit (writes ~/.streamlit/), Python caches, and bcrypt.
    HOME=/tmp \
    BUDGET_DATA_DIR=/app/data

# /app/data is a volume — transactions and users.json survive container restarts
VOLUME ["/app/data"]
EXPOSE 8501

USER appuser

# Streamlit health endpoint — Docker marks container unhealthy until it responds
HEALTHCHECK --interval=30s --timeout=10s --start-period=20s --retries=3 \
    CMD python -c \
        "import urllib.request, sys; \
         urllib.request.urlopen('http://localhost:8501/_stcore/health') or sys.exit(1)"

CMD ["python", "-m", "streamlit", "run", "src/budget_tracker/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]
