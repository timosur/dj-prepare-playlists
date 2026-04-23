FROM --platform=linux/amd64 python:3.12-slim

# System deps for audio processing
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Install essentia from prebuilt wheel (x86_64 Linux only)
RUN pip install --no-cache-dir essentia

WORKDIR /app

# Install dj-cli dependencies first (cache layer)
COPY pyproject.toml .
RUN pip install --no-cache-dir .

# Copy source code
COPY dj_cli/ dj_cli/

# Reinstall with source
RUN pip install --no-cache-dir -e .

# Mount points for data and music library
VOLUME ["/data", "/music"]

ENTRYPOINT ["dj"]
