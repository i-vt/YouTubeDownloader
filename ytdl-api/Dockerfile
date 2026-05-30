FROM python:3.12-slim

LABEL maintainer="ytdl-api"
LABEL description="CLI wrapper for y2save.com — downloads audio/video via y2save's backend API"

WORKDIR /app

# Install only what's needed (requests for HTTP, rich for pretty output)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source
COPY y2save_client.py .
COPY cli/ytdl.py      .

# Make CLI executable and on PATH
RUN chmod +x ytdl.py && \
    ln -s /app/ytdl.py /usr/local/bin/ytdl

# Default output directory (mount a volume here)
RUN mkdir -p /downloads
VOLUME ["/downloads"]
WORKDIR /downloads

ENTRYPOINT ["python", "/app/ytdl.py"]
CMD ["--help"]
