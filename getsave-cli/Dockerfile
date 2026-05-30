FROM python:3.12-slim

# Avoid .pyc clutter and unbuffered stdout for live progress bars.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install ca-certs for HTTPS to the API and to googlevideo CDN.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY getsave.py .
RUN chmod +x getsave.py

# Default landing point for downloaded files; mount a host dir here.
VOLUME ["/downloads"]
WORKDIR /downloads

ENTRYPOINT ["python", "/app/getsave.py"]
CMD ["--help"]
