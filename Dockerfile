# Runtime is read-only Monad mode; no issuer keys or local signing API.
FROM python:3.12-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.4@sha256:d0a6eca6c669dc7e9c51218707b8438a3d30402733d739dcc00adb3e213e8f5c /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
COPY pyproject.toml uv.lock README.zh-CN.md LICENSE ./
COPY src ./src
RUN uv sync --locked --no-dev --no-default-groups --no-editable

FROM python:3.12-slim-trixie@sha256:dddfd7e07f9d15aeeca61529320492139d21cac7f0070c00609243e51e4e0016
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
USER 10001:10001
EXPOSE 8765
HEALTHCHECK --interval=30s --timeout=20s --start-period=60s --retries=3 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=18).read()"]
ENTRYPOINT ["python", "-m", "prooftrail"]
CMD ["serve", "--mode", "monad", "--host", "0.0.0.0", "--port", "8765"]
