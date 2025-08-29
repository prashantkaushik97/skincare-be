FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# (optional) if you don't build native deps, you can remove build-essential
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# ensure gunicorn is present (either here or put it in requirements.txt)
RUN pip install --no-cache-dir -r requirements.txt gunicorn

COPY . .

ENV PORT=8080 \
    WEB_CONCURRENCY=2 \
    GUNICORN_THREADS=8
EXPOSE 8080

# Use the Flask factory in app/__init__.py
# (sh -c so env vars expand; factory form 'module:create_app()' is supported)
CMD ["sh","-c","gunicorn -w ${WEB_CONCURRENCY:-2} --threads ${GUNICORN_THREADS:-8} -b 0.0.0.0:${PORT:-8080} 'app:create_app()'"]
