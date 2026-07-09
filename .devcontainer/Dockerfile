# Dev-only image: no COPY of source or pyproject.toml here — the workspace is
# bind-mounted over /app at runtime, so dependency install happens in
# postCreateCommand (devcontainer.json) instead of at build time. This is the
# opposite of ../Dockerfile, which is production-only (--no-dev, strips tests).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1

WORKDIR /app

CMD ["sleep", "infinity"]
