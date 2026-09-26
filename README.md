# YouTubeDownloader

Two small, self-contained CLI tools for downloading YouTube (and other sites') video and audio — **no local `yt-dlp` or `ffmpeg` required**. Each tool replicates the request flow of a public web downloader service, so all fetching/processing happens on that service's servers; the CLI just asks for the file and streams it to disk.

| Tool | Backend service | Best for |
|------|-----------------|----------|
| [`getsave-cli`](#1-getsave-cli) | get-save.com | Video downloads with a resolution picker; many source sites |
| [`ytdl-api`](#2-ytdl-api) | y2save.com | MP3/audio extraction, up-to-4K video, dubbed audio tracks, batch jobs |

> ⚠️ **Legal note:** Only download content you have the rights to. Grabbing third-party copyrighted videos violates YouTube's Terms of Service and likely infringes the rights-holder's copyright. These tools are provided for content you own or are permitted to download.

---

## Repository layout

```
YouTubeDownloader/
├── getsave-cli/            # CLI for the get-save.com service
│   ├── getsave.py          #   main script (Python 3, requests + tqdm)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── docker-compose.yml
└── ytdl-api/               # CLI wrapper for y2save.com's backend
    ├── y2save_client.py    #   API client library
    ├── cli/ytdl.py         #   CLI entry point
    ├── batch_download.sh   #   parallel batch downloader (MP3 by default)
    ├── requirements.txt
    ├── Dockerfile
    └── docker-compose.yml
```

## Prerequisites

- **Recommended:** Docker (each tool ships with its own `Dockerfile` and `docker-compose.yml`)
- **Alternative:** Python 3.10+ and `pip` for running the scripts directly

---

## 1. getsave-cli

Downloads videos via the **get-save.com** service. The script POSTs the source URL to `api.get-save.com`, picks the format closest to your requested resolution from the returned list, and downloads it (YouTube downloads are routed through the service's proxy so they don't 403).

### Build

```bash
cd getsave-cli
docker build -t getsave-cli .
```

### How to use

```bash
# Download at 1080p (default) into ./downloads
docker run --rm -v "$PWD/downloads:/downloads" getsave-cli \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Pick a specific quality — the closest available match wins
docker run --rm -v "$PWD/downloads:/downloads" getsave-cli \
  -q 720 "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# List available formats without downloading
docker run --rm getsave-cli -l "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Dump the raw API response (handy for debugging unsupported sites)
docker run --rm getsave-cli --json "https://example.com/video"

# Override the output filename
docker run --rm -v "$PWD/downloads:/downloads" getsave-cli \
  --filename "my-clip" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Or via docker compose (the service sits behind the `cli` profile):

```bash
docker compose run --rm getsave "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

Without Docker:

```bash
cd getsave-cli
pip install -r requirements.txt        # requests, tqdm
python getsave.py -o ./downloads "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

> Note: the default output directory is `/downloads` (the Docker volume), so pass `-o` when running outside Docker.

### Options

| Flag | Description |
|------|-------------|
| `url` | Source video URL (required) |
| `-q, --quality <height>` | Target height in px: `144 240 360 480 720 1080 1440 2160 4320` (default: `1080`). Snaps to the closest available format, preferring lower over higher. |
| `-o, --output <dir>` | Output directory (default: `/downloads`) |
| `-l, --list` | List available formats and exit |
| `--json` | Print the raw API response and exit |
| `--filename <name>` | Override the output filename (without extension) |

### Supported sites

YouTube, VK, Yandex, RuTube, Telegram, Odnoklassniki, Mail.ru video, Dzen, Smotrim, Pinterest, TikTok, Instagram, and more — anything the get-save.com website can handle. Private, age-gated, or region-locked videos will fail with an empty format list.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `2` | API request failed (both endpoints) |
| `3` | API responded but had no downloadable formats |
| `4` | Quality selection failed |
| `5` | The download itself failed (network, 403, etc.) |

---

## 2. ytdl-api

CLI wrapper for **y2save.com**'s backend (`ytdl.y2mp3.co`). It submits a conversion job, polls until the server finishes, then streams the file down. If the primary endpoint fails, it retries via a fallback endpoint (`hub.ytconvert.org`).

### Build

```bash
cd ytdl-api
docker build -t ytdl-api .
```

### How to use

```bash
# List every supported format key
docker run --rm ytdl-api formats

# Download MP4 720p (default format)
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download MP3 at 320 kbps
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format mp3-320

# Download 1080p MP4
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format mp4-1080

# Download with a dubbed/translated audio track (where available)
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format mp4-720 --translated

# Save to a specific filename
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format flac -o /downloads/mysong.flac
```

Or via docker compose:

```bash
docker compose run --rm ytdl "https://youtu.be/..." --format mp3-128
docker compose run --rm ytdl formats
```

Without Docker (Python 3.10+):

```bash
cd ytdl-api
pip install -r requirements.txt        # requests
python cli/ytdl.py formats
python cli/ytdl.py "https://youtu.be/..." --format mp4-720
```

### Options

| Flag | Description |
|------|-------------|
| `url` | YouTube or supported-site URL (the `download` keyword is optional: `ytdl <url>` works) |
| `-f, --format <key>` | Format key (default: `mp4-720`) — see tables below |
| `-t, --translated` | Download the dubbed/translated audio track where the source video offers one |
| `-o, --output <path>` | Save file to this path (default: server-provided filename in the working directory) |
| `formats` | Sub-command: list all supported format keys |

### Audio formats

| Key | Description |
|-----|-------------|
| `mp3-320` | MP3 320 kbps |
| `mp3-192` | MP3 192 kbps |
| `mp3-128` | MP3 128 kbps |
| `mp3-64`  | MP3 64 kbps |
| `wav`     | WAV 128 kbps |
| `m4a`     | M4A 128 kbps |
| `ogg`     | OGG 128 kbps |
| `opus`    | Opus 128 kbps |
| `flac`    | FLAC lossless |

### Video formats

| Key | Description |
|-----|-------------|
| `mp4-2160` | MP4 4K |
| `mp4-1440` | MP4 2K |
| `mp4-1080` | MP4 1080p |
| `mp4-720`  | MP4 720p (default) |
| `mp4-480`  | MP4 480p |
| `mp4-360`  | MP4 360p |
| `mp4-144`  | MP4 144p |
| `webm-*`   | Same resolutions in WebM |
| `mkv-*`    | Same resolutions in MKV |

### Batch downloads

`batch_download.sh` downloads every YouTube URL in a text file (default format: MP3-320), in parallel, with resume support. It requires the `ytdl-api` Docker image to be built first.

```bash
cd ytdl-api
docker build -t ytdl-api .              # required once

# One URL per line in youtube_links.txt, then:
./batch_download.sh                     # reads ./youtube_links.txt
./batch_download.sh /path/to/links.txt  # custom list file

# Tune via environment variables:
WORKERS=5 FORMAT=mp4-720 OUTPUT_DIR=./videos ./batch_download.sh
```

| Variable | Default | Description |
|----------|---------|-------------|
| `OUTPUT_DIR` | `./downloads` | Where files land |
| `FORMAT` | `mp3-320` | Any format key from the tables above |
| `WORKERS` | `3` | Number of parallel downloads |

The script skips URLs that already succeeded (tracked in `downloads/.done_urls`), logs everything to `downloads/download.log`, and collects failures in `downloads/failed.txt` so you can re-run it safely.

---

## Troubleshooting

- **403 / failed downloads (getsave-cli):** YouTube's tokenized URLs expire quickly — don't wait between fetching info and downloading. The get-save proxy can also rate-limit you.
- **"No downloadable formats":** the video is likely private, age-gated, or region-locked, or the site isn't supported.
- **Job never finishes (ytdl-api):** polling times out after 300 s; re-run the command or try a different format.
- **Batch script exits immediately:** make sure the `ytdl-api` image is built and your links file contains lines starting with `http` that point at `youtube.com/watch` or `youtu.be/`.

## Caveats

- Both tools depend on free third-party services with no SLA. They can rate-limit, change their APIs, or disappear at any time — if a tool suddenly stops working, the upstream service probably changed.
- This isn't `yt-dlp`. If you need something actively maintained and self-contained, that's the answer.
