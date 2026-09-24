# Playwright needs a real headless Chromium, which is why this can't be a
# plain "pip install -r requirements.txt" buildpack deploy -- it needs a
# container that can install browser binaries and their OS-level libraries.
# `playwright install --with-deps` below handles both in one step, provided
# the base image is Debian/Ubuntu-family (it is).
FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install --with-deps chromium

COPY . .

RUN mkdir -p instance/reports

ENV PYTHONUNBUFFERED=1
EXPOSE 10000

# Render sets $PORT; default to 10000 for local `docker run` testing.
# --timeout 180: report generation (PDF + carousel + postcard) genuinely
# takes tens of seconds, sometimes more on a cold instance -- gunicorn's
# 30s default would kill the worker mid-request on a slow one.
CMD gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 180 app:app
