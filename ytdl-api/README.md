# ytdl-api

CLI wrapper for **y2save.com**'s backend (`ytdl.y2mp3.co`).  
No local ffmpeg, no yt-dlp — everything is processed on y2save's servers.

---

## Quick start (Docker — recommended)

```bash
# Build once
docker build -t ytdl-api .

# List supported formats
docker run --rm ytdl-api formats

# Download MP4 720p (default)
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Download MP3 320kbps
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format mp3-320

# Download 1080p MP4
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format mp4-1080

# Download with translated audio track
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format mp4-720 --translated

# Save to a specific filename
docker run --rm -v "$PWD/downloads:/downloads" ytdl-api \
    "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --format flac -o /downloads/mysong.flac
```

Or with **docker compose**:

```bash
docker compose run --rm ytdl "https://youtu.be/..." --format mp3-128
```

---

## Without Docker (Python 3.10+)

```bash
pip install requests
python cli/ytdl.py formats
python cli/ytdl.py "https://youtu.be/..." --format mp4-720
```

---

## All options

```
usage: ytdl [-h] {formats,download} ...  OR  ytdl <url> [options]

positional:
  url                    YouTube or supported-site URL

options:
  -f, --format FORMAT    Format key (default: mp4-720)
  -t, --translated       Download dubbed/translated audio track where available
  -o, --output PATH      Save file to this path (default: server filename in cwd)
  -h, --help             Show this message

sub-commands:
  formats                List all supported format keys
  download               Explicit download sub-command
```

---

## Audio formats

| Key        | Description        |
|------------|--------------------|
| `mp3-320`  | MP3 320 kbps       |
| `mp3-192`  | MP3 192 kbps       |
| `mp3-128`  | MP3 128 kbps       |
| `mp3-64`   | MP3 64 kbps        |
| `wav`      | WAV 128 kbps       |
| `m4a`      | M4A 128 kbps       |
| `ogg`      | OGG 128 kbps       |
| `opus`     | Opus 128 kbps      |
| `flac`     | FLAC lossless      |

## Video formats

| Key         | Description   |
|-------------|---------------|
| `mp4-2160`  | MP4 4K        |
| `mp4-1440`  | MP4 2K        |
| `mp4-1080`  | MP4 1080p     |
| `mp4-720`   | MP4 720p ✓    |
| `mp4-480`   | MP4 480p      |
| `mp4-360`   | MP4 360p      |
| `mp4-144`   | MP4 144p      |
| `webm-*`    | Same in WebM  |
| `mkv-*`     | Same in MKV   |

---

## How it works

1. **Submit** — `POST https://ytdl.y2mp3.co/api/v2/download`  
   Body mirrors what y2save.com sends from its own front-end.
2. **Poll** — `GET https://ytdl.y2mp3.co/api/status/{id}` every 3 s until `status == "done"`.
3. **Download** — streams the finished file from the URL returned by step 2.
4. **Fallback** — if the primary endpoint fails, retries via `hub.ytconvert.org/api/download`.

---

## `--translated` flag

Passes `"translated": true` in the request body — the same flag the y2save.com
front-end sends when the user selects a dubbed audio track from the language picker.
Whether a translated track is available depends entirely on the source video.
