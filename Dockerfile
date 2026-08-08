# ---- build stage ----
FROM python:3.12-slim AS builder
WORKDIR /app
ENV PIP_NO_CACHE_DIR=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# ---- runtime stage ----
FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PATH=/home/appuser/.local/bin:$PATH

# non-root user — never run containers as root
RUN adduser --disabled-password --gecos "" appuser
COPY --from=builder /root/.local /home/appuser/.local
COPY --chown=appuser:appuser . .
USER appuser

EXPOSE 8080
# Cloud Run provides $PORT; default 8080. Gunicorn + uvicorn workers.
CMD exec gunicorn app.main:app \
    --worker-class uvicorn.workers.UvicornWorker \
    --workers 2 --bind 0.0.0.0:${PORT:-8080} \
    --timeout 60 --access-logfile - --error-logfile -
