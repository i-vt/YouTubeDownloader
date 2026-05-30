"""
y2save_client.py — Reverse-engineered client for y2save.com's backend APIs.

Primary:  https://ytdl.y2mp3.co/api/v2/download  +  /api/status/{id}
Fallback: https://hub.ytconvert.org/api/download
"""

import time
import requests

# ── Constants ────────────────────────────────────────────────────────────────

PRIMARY_URL  = "https://ytdl.y2mp3.co/api/v2/download"
STATUS_URL   = "https://ytdl.y2mp3.co/api/status/{id}"
FALLBACK_URL = "https://hub.ytconvert.org/api/download"

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer":         "https://www.y2save.com/",
    "Origin":          "https://www.y2save.com",
    "Accept":          "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type":    "application/json",
    "sec-ch-ua":       '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile":   "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# ── Format helpers ────────────────────────────────────────────────────────────

AUDIO_FORMATS = {
    "mp3-320": ("audio", "mp3", "320k"),
    "mp3-192": ("audio", "mp3", "192k"),
    "mp3-128": ("audio", "mp3", "128k"),
    "mp3-64":  ("audio", "mp3", "64k"),
    "wav":     ("audio", "wav", "128k"),
    "m4a":     ("audio", "m4a", "128k"),
    "ogg":     ("audio", "ogg", "128k"),
    "opus":    ("audio", "opus","128k"),
    "flac":    ("audio", "flac","128k"),
}

VIDEO_FORMATS = {
    "mp4-2160": ("video", "mp4",  "2160p"),
    "mp4-1440": ("video", "mp4",  "1440p"),
    "mp4-1080": ("video", "mp4",  "1080p"),
    "mp4-720":  ("video", "mp4",  "720p"),
    "mp4-480":  ("video", "mp4",  "480p"),
    "mp4-360":  ("video", "mp4",  "360p"),
    "mp4-144":  ("video", "mp4",  "144p"),
    "webm-2160":("video", "webm", "2160p"),
    "webm-1440":("video", "webm", "1440p"),
    "webm-1080":("video", "webm", "1080p"),
    "webm-720": ("video", "webm", "720p"),
    "webm-480": ("video", "webm", "480p"),
    "webm-360": ("video", "webm", "360p"),
    "webm-144": ("video", "webm", "144p"),
    "mkv-2160": ("video", "mkv",  "2160p"),
    "mkv-1440": ("video", "mkv",  "1440p"),
    "mkv-1080": ("video", "mkv",  "1080p"),
    "mkv-720":  ("video", "mkv",  "720p"),
    "mkv-480":  ("video", "mkv",  "480p"),
    "mkv-360":  ("video", "mkv",  "360p"),
    "mkv-144":  ("video", "mkv",  "144p"),
}

ALL_FORMATS = {**AUDIO_FORMATS, **VIDEO_FORMATS}


def resolve_format(fmt: str):
    """Return (type, format, quality) tuple for a format key, or raise ValueError."""
    key = fmt.lower().strip()
    if key not in ALL_FORMATS:
        raise ValueError(
            f"Unknown format '{fmt}'.\n"
            f"Audio: {', '.join(sorted(AUDIO_FORMATS))}\n"
            f"Video: {', '.join(sorted(VIDEO_FORMATS))}"
        )
    return ALL_FORMATS[key]


# ── Primary API ───────────────────────────────────────────────────────────────

def _build_primary_payload(url: str, fmt: str, translated: bool) -> dict:
    kind, fmt_name, quality = resolve_format(fmt)
    payload = {
        "url":    url,
        "output": {
            "type":    kind,
            "format":  fmt_name,
            "quality": quality,
        },
    }
    if kind == "audio":
        payload["audio"] = {"bitrate": quality}
    if translated:
        payload["translated"] = True
    return payload


def _build_fallback_payload(url: str, fmt: str, translated: bool) -> dict:
    kind, fmt_name, quality = resolve_format(fmt)
    payload = {
        "url":    url,
        "os":     "windows",
        "output": {
            "type":    kind,
            "format":  fmt_name,
            "quality": quality,
        },
        "audio":  {"bitrate": "128k"},
    }
    if translated:
        payload["translated"] = True
    return payload


def start_job(url: str, fmt: str, translated: bool = False) -> dict:
    """
    POST to y2save primary API.  Returns the raw JSON response (contains job id).
    Falls back to hub.ytconvert.org if primary fails.
    """
    payload = _build_primary_payload(url, fmt, translated)
    resp = requests.post(PRIMARY_URL, json=payload, headers=HEADERS, timeout=30)

    if resp.status_code == 200:
        return resp.json()

    # Fallback
    payload2 = _build_fallback_payload(url, fmt, translated)
    resp2 = requests.post(FALLBACK_URL, json=payload2, headers=HEADERS, timeout=30)
    resp2.raise_for_status()
    return resp2.json()


def poll_status(job_id: str, interval: float = 3.0, timeout: float = 300.0) -> dict:
    """
    Poll /api/status/{id} until status == 'done' or timeout.
    Returns the final status dict (which includes the download URL).
    """
    endpoint = STATUS_URL.format(id=job_id)
    deadline = time.time() + timeout

    while time.time() < deadline:
        resp = requests.get(endpoint, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status", "").lower()
        if status in ("done", "finished", "completed"):
            return data
        if status in ("error", "failed"):
            raise RuntimeError(f"Server reported failure: {data}")

        time.sleep(interval)

    raise TimeoutError(f"Job {job_id} did not finish within {timeout}s")


def download_file(download_url: str, dest_path: str, progress_cb=None) -> str:
    """
    Stream the finished file to dest_path.
    progress_cb(bytes_done, total_bytes) is called if provided.
    Returns dest_path.
    """
    resp = requests.get(download_url, headers=HEADERS, stream=True, timeout=60)
    resp.raise_for_status()

    total = int(resp.headers.get("content-length", 0))
    done  = 0

    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                f.write(chunk)
                done += len(chunk)
                if progress_cb:
                    progress_cb(done, total)

    return dest_path
