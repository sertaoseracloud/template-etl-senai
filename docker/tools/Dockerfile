FROM python:3.11-slim

# Repository is bind-mounted read-only; bytecode writes would fail noisily.
ENV PYTHONDONTWRITEBYTECODE=1
# Lean step output in run.sh needs Python output as it happens, not at process exit.
ENV PYTHONUNBUFFERED=1
# ruff would otherwise try to write .ruff_cache into the read-only mount.
ENV RUFF_CACHE_DIR=/tmp/ruff-cache

WORKDIR /workspace

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
