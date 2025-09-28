# Use a supported base (Debian 12 “bookworm”) to avoid EOL CVEs
FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Create non-root user early
RUN useradd -m -u 10001 appuser

# Install Python deps; upgrade pip/setuptools to fix known CVEs
COPY requirements.txt .
RUN python -m pip install --upgrade pip "setuptools>=78.1.1" wheel \
 && pip install -r requirements.txt

# Copy app last to maximize layer cache
COPY app /app/app

USER appuser
EXPOSE 8000
CMD ["uvicorn","app.main:app","--host","0.0.0.0","--port","8000"]
