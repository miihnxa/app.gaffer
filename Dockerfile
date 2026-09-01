# Gaffer Cloud
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/src \
    GAFFER_DB=/data/gaffer.sqlite3

WORKDIR /app

COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt

COPY src/ ./src/
COPY config/season-plan.yaml config/watchlist.yaml ./config/
COPY config/settings.example.yaml ./config/settings.yaml

# SQLite lives on a mounted volume so subscriptions survive a redeploy.
RUN mkdir -p /data
VOLUME /data

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=4)"

# One worker, several threads: the FPL data cache is per-process, and more
# workers would mean more duplicate calls out to the FPL API.
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", \
     "--timeout", "90", "--access-logfile", "-", \
     "fpl.cloud.app:create_app()"]
