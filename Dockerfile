FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY scripts ./scripts
COPY aegra.json langgraph.json README.md ./
RUN uv sync --frozen --no-dev

EXPOSE 2024

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD uv run --no-sync python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:2024/health', timeout=3).read()"

CMD ["uv", "run", "--no-sync", "uvicorn", "aegra_api.main:app", "--host", "0.0.0.0", "--port", "2024"]
