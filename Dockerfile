# syntax=docker/dockerfile:1

FROM node:22-alpine AS web-build
WORKDIR /web

COPY web/package.json web/yarn.lock web/.yarnrc.yml ./
RUN corepack yarn install --immutable

COPY web/ ./
RUN corepack yarn build

FROM python:3.12-slim

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    AGENT_RELAY_SERVER__HOST=0.0.0.0 \
    AGENT_RELAY_SERVER__PORT=80

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY config ./config
COPY alembic.ini ./alembic.ini
COPY migrations ./migrations

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir uv==0.12.5 \
    && uv sync --locked --no-dev --no-editable \
    && useradd --create-home --uid 10001 appuser \
    && install -d -o appuser -g appuser /app/logs /app/data

COPY --from=web-build /web/dist ./static

USER appuser
EXPOSE 80
CMD ["python", "-m", "agent_relay.server"]
