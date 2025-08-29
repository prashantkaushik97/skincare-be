# ---- Build stage (optional but keeps final image smaller) ----
FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/home/appuser/.local/bin:$PATH

# System deps only if you compile wheels (comment out if not needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN useradd -m appuser
WORKDIR /app

# Install deps first for layer caching
COPY requirements.txt .
RUN pip install --user -r requirements.txt

# Copy app code (don’t copy venv or secrets – see .dockerignore below)
COPY . .

# Use non-root
USER appuser

# Cloud Run will inject $PORT. Default to 8080 for local runs.
ENV PORT=8080
EXPOSE 8080

# If run.py exposes "app = FastAPI(...)" at module top-level, this is perfect:
# You can switch to gunicorn if you want (commented example below).
CMD ["uvicorn", "run:app", "--host", "0.0.0.0", "--port", "8080"]

# ---- Alternative (uncomment to use Gunicorn + Uvicorn workers) ----
# CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "-w", "1", "-b", "0.0.0.0:8080", "run:app"]
