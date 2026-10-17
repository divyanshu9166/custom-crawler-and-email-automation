ARG PYTHON_BASE_IMAGE=python:3.13-slim-bookworm
FROM ${PYTHON_BASE_IMAGE}
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
WORKDIR /app
COPY requirements.lock pyproject.toml ./
RUN pip install --no-cache-dir -r requirements.lock
ARG INSTALL_BROWSER=true
RUN if [ "$INSTALL_BROWSER" = "true" ]; then python -m playwright install --with-deps chromium; fi
COPY outreach ./outreach
COPY scripts ./scripts
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home outreach && mkdir -p /data && chown outreach:outreach /data
ENV DATA_DIR=/data
USER outreach
EXPOSE 8000
CMD ["uvicorn", "outreach.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
