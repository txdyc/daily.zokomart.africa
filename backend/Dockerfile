FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/opt/ms-playwright

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
# --no-install-project: app/ is not copied yet; only third-party deps go in this layer
RUN uv sync --frozen --no-dev --no-install-project

# Chromium is required: article fetching (Crawl4AI) and listing-page discovery
# (fetch_text_rendered) both depend on it.
RUN uv run playwright install --with-deps chromium

COPY app ./app
COPY docker-entrypoint.sh ./
RUN chmod +x docker-entrypoint.sh

EXPOSE 8000
ENTRYPOINT ["./docker-entrypoint.sh"]
