ARG PYTHON_BASE_IMAGE=python:3.13-slim-bookworm
FROM ${PYTHON_BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright DATA_DIR=/data DISPLAY=:99
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock && python -m playwright install --with-deps chromium \
    && apt-get update && apt-get install -y --no-install-recommends xvfb xauth x11vnc novnc websockify \
    && rm -rf /var/lib/apt/lists/*
COPY outreach ./outreach
COPY scripts ./scripts
COPY deploy/platform-browser-setup.sh /app/platform-browser-setup.sh
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home outreach && mkdir -p /data && chown outreach:outreach /data && chmod +x /app/platform-browser-setup.sh
USER outreach
ENTRYPOINT ["/app/platform-browser-setup.sh"]
