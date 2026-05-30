#!/usr/bin/env python3
"""
getsave - CLI for downloading videos via the get-save.com service.

Reverse-engineered from the site's front-end JavaScript captured in a HAR file.
The flow is: POST the source URL to api.get-save.com, pick a format from the
returned `sizes` array, then GET the resulting media URL. For YouTube the file
URL is rewritten through proxy.get-save.com (otherwise it 403s without the
right referer).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from tqdm import tqdm

API_PRIMARY = "https://api.get-save.com/api/v1/vidinfo"
API_FALLBACK = "https://api-cdn.get-save.com/api/v1/vidinfo"
PROXY_PREFIX = "https://proxy.get-save.com/"

# Matches the in-browser User-Agent so the API doesn't get suspicious.
DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64; rv:140.0) "
    "Gecko/20100101 Firefox/140.0"
)

# Quality buckets exposed by the site UI.
QUALITY_LADDER = [4320, 2160, 1440, 1080, 720, 480, 360, 240, 144]


class GetSaveError(RuntimeError):
    pass


def is_youtube(url: str) -> bool:
    return "youtu" in url.lower()


def fetch_video_info(url: str, timeout: int = 30) -> dict[str, Any]:
    """Query the get-save API for available formats. Tries primary then CDN."""
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": DEFAULT_UA,
        "Origin": "https://ru.get-save.com",
        "Referer": "https://ru.get-save.com/",
    }
    payload = {"url": url}
    last_error: Exception | None = None

    for endpoint in (API_PRIMARY, API_FALLBACK):
        try:
            response = requests.post(
                endpoint, json=payload, headers=headers, timeout=timeout
            )
            response.raise_for_status()
            data = response.json()
            if not data.get("sizes"):
                raise GetSaveError(
                    f"API returned no formats. Raw response: {data}"
                )
            return data
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            continue

    raise GetSaveError(
        f"Both API endpoints failed. Last error: {last_error}"
    )


def filter_valid_videos(sizes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep entries that look like fully-muxed, downloadable videos.

    Mirrors the front-end's filtering: drop 3gp/m4a audio-only/opus-only and
    anything that isn't served over HTTP(S).
    """
    valid = []
    for item in sizes:
        if item.get("protocol") not in {"http", "https"}:
            continue
        if item.get("ext") in {"3gp", "m4a"}:
            continue
        if item.get("acodec") in {"none", "opus"}:
            continue
        if not item.get("url"):
            continue
        valid.append(item)
    return valid


def find_closest_quality(
    target_height: int, videos: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Pick the entry matching the target resolution, then step down, then up."""
    if not videos:
        return None
    exact = [v for v in videos if v.get("height") == target_height]
    if exact:
        # Prefer the smallest file at the chosen height (mp4 > webm typically).
        return min(exact, key=lambda v: v.get("filesize") or float("inf"))
    below = sorted(
        [v for v in videos if (v.get("height") or 0) < target_height],
        key=lambda v: v.get("height") or 0,
        reverse=True,
    )
    if below:
        return below[0]
    above = sorted(
        [v for v in videos if (v.get("height") or 0) > target_height],
        key=lambda v: v.get("height") or 0,
    )
    return above[0] if above else None


def sanitize_filename(name: str, fallback: str = "video") -> str:
    """Strip characters that would upset the filesystem or the proxy."""
    cleaned = re.sub(r"[^\w\s\-]", "", name, flags=re.UNICODE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or fallback


def build_download_url(media_url: str, title: str, source_url: str) -> str:
    """For YouTube the site reroutes through proxy.get-save.com and appends a
    title query param. For other hosts the raw URL works directly."""
    if not is_youtube(source_url):
        return media_url
    rerouted = re.sub(r"^https://", PROXY_PREFIX, media_url)
    safe_title = sanitize_filename(title)
    rerouted += "&title=" + urllib.parse.quote(safe_title) + " [get.gt]"
    return rerouted


def download(url: str, output_path: Path, chunk: int = 1 << 15) -> None:
    """Stream a remote file to disk with a progress bar."""
    headers = {
        "User-Agent": DEFAULT_UA,
        "Referer": "https://ru.get-save.com/",
    }
    with requests.get(url, headers=headers, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        total = int(resp.headers.get("Content-Length", 0)) or None
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as fh, tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=output_path.name,
            leave=True,
        ) as bar:
            for block in resp.iter_content(chunk_size=chunk):
                if not block:
                    continue
                fh.write(block)
                bar.update(len(block))


def print_formats(videos: list[dict[str, Any]]) -> None:
    print(f"{'idx':>4}  {'height':>6}  {'ext':>5}  {'size':>10}  url")
    for idx, v in enumerate(videos):
        size = v.get("filesize")
        size_s = f"{size/1024/1024:.1f}MB" if size else "?"
        print(
            f"{idx:>4}  {v.get('height', '?'):>6}  "
            f"{v.get('ext', '?'):>5}  {size_s:>10}  "
            f"{v.get('url', '')[:60]}..."
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="getsave",
        description=(
            "Download videos via the get-save.com service. "
            "Supports YouTube and the other hosts the site recognizes."
        ),
    )
    parser.add_argument("url", help="Source video URL (e.g. YouTube link).")
    parser.add_argument(
        "-q", "--quality",
        type=int,
        default=1080,
        help=(
            "Target height in pixels (default: 1080). "
            "Falls back to the closest available."
        ),
    )
    parser.add_argument(
        "-o", "--output",
        type=Path,
        default=Path("/downloads"),
        help="Output directory (default: /downloads).",
    )
    parser.add_argument(
        "-l", "--list",
        action="store_true",
        help="List available formats and exit without downloading.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Dump the raw API response to stdout and exit.",
    )
    parser.add_argument(
        "--filename",
        type=str,
        default=None,
        help="Override the output filename (without extension).",
    )
    args = parser.parse_args()

    try:
        info = fetch_video_info(args.url)
    except GetSaveError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if args.json:
        json.dump(info, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0

    videos = filter_valid_videos(info.get("sizes", []))
    if not videos:
        print(
            "error: no downloadable formats. The site likely can't handle "
            "this URL (private/age-gated/region-locked).",
            file=sys.stderr,
        )
        return 3

    if args.list:
        title = info.get("meta", {}).get("title", "(no title)")
        print(f"title: {title}")
        print_formats(videos)
        return 0

    chosen = find_closest_quality(args.quality, videos)
    if not chosen:
        print("error: could not pick a format", file=sys.stderr)
        return 4

    title = info.get("meta", {}).get("title") or args.url
    safe_title = sanitize_filename(args.filename or title)
    ext = chosen.get("ext", "mp4")
    output_path = args.output / f"{safe_title}.{ext}"

    media_url = build_download_url(chosen["url"], title, args.url)
    print(
        f"chosen: {chosen.get('height')}p {ext} "
        f"({(chosen.get('filesize') or 0)/1024/1024:.1f} MB)"
    )
    print(f"saving to: {output_path}")

    try:
        download(media_url, output_path)
    except requests.RequestException as exc:
        print(f"error: download failed: {exc}", file=sys.stderr)
        return 5

    print("done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
