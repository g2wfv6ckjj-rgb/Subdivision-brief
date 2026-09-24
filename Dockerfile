# Base image: Microsoft's own Playwright-for-Python image. It ships Chromium
# and every OS-level library Playwright needs ALREADY INSTALLED and
# version-matched. This replaces the previous approach of installing those
# dependencies into `python:3.11-slim` ourselves via
# `playwright install --with-deps chromium`, which is what failed during the
# first Render deploy (exit code 1, "process ... did not complete
# successfully"). `python:3.11-slim` is a rolling tag -- the Debian release
# underneath it moves forward on its own over time -- and the Playwright
# version pinned in requirements.txt had a dependency-installer script that
# didn't recognize whatever Debian release Render's build pulled. Starting
# from Microsoft's own image instead makes that compatibility Microsoft's
# problem to keep solved, not this Dockerfile's.
#
# The Playwright version in requirements.txt MUST match this tag's version
# exactly (1.57.0 here, 1.57.0 there). Playwright is strict about the Python
# package matching the installed browser build -- a mismatch here is a
# different, more confusing failure than the one this fixes, not a smaller
# version of the same one.
FROM mcr.microsoft.com/playwright/python:v1.57.0-noble

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# No `playwright install` step needed here -- see above; the base image
# already has a matched Chromium build sitting in it.

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 10000

# --timeout 180: report generation (PDF + carousel + postcard) genuinely
# takes tens of seconds, sometimes more on a cold instance -- gunicorn's
# 30s default would kill the worker mid-request on a slow one.
CMD gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 2 --timeout 180 app:app
