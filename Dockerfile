# syntax=docker/dockerfile:1.7

# ---------- builder: install Python deps (gevent needs build tools) ----------
FROM python:3.13-slim AS builder
WORKDIR /app

RUN apt-get update \
  && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# ---------- runner: minimal runtime ----------
FROM python:3.13-slim AS runner
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/home/appuser/.local/bin:$PATH \
    DATABASE_PATH=/app/.data/timerrr.db \
    PORT=5001

RUN useradd --system --uid 1001 --create-home appuser

COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .

RUN mkdir -p /app/.data && chown -R appuser:appuser /app/.data
VOLUME ["/app/.data"]

USER appuser
EXPOSE 5001
CMD ["gunicorn", \
     "--worker-class", "geventwebsocket.gunicorn.workers.GeventWebSocketWorker", \
     "--workers", "1", \
     "--bind", "0.0.0.0:5001", \
     "wsgi:application"]
