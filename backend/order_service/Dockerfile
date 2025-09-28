# week09/example-2/backend/order_service/Dockerfile

# Use a newer Debian base to reduce CVEs compared with buster
FROM python:3.10-slim-bookworm

# Sensible Python defaults and no pip cache
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Create a non-root user
RUN addgroup --system app && adduser --system --ingroup app --uid 10001 appuser

# App directory
WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application code
COPY app ./app

# Ensure the app dir is owned by the non-root user
RUN chown -R appuser:app /app

# Drop privileges
USER appuser

# Expose FastAPI port
EXPOSE 8000

# Lightweight healthcheck without adding curl/wget
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
  CMD python - <<'PY' || exit 1
import urllib.request, sys
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=2) as r:
        sys.exit(0 if r.status == 200 else 1)
except Exception:
    sys.exit(1)
PY

# Start the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
