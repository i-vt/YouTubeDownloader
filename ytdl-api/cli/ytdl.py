#!/usr/bin/env python3
"""
ytdl — CLI to download via y2save.com's backend.

Usage examples:
  ytdl  "https://youtu.be/xyz"                         # default: mp4-720
  ytdl  "https://youtu.be/xyz"  --format mp3-320
  ytdl  "https://youtu.be/xyz"  --format mp4-1080
  ytdl  "https://youtu.be/xyz"  --format flac
  ytdl  "https://youtu.be/xyz"  --format mp4-720  --translated
  ytdl  "https://youtu.be/xyz"  --format mp3-128  -o ~/Music/song.mp3
  ytdl  formats                                        # list all formats
"""

import os
import sys
import time
import argparse

from y2save_client import (
    ALL_FORMATS, AUDIO_FORMATS, VIDEO_FORMATS,
    resolve_format, start_job, poll_status, download_file,
)

# ── Colour helpers ────────────────────────────────────────────────────────────

def _c(code, text):
    if sys.stdout.isatty():
        return f"\033[{code}m{text}\033[0m"
    return text

green  = lambda t: _c("32", t)
yellow = lambda t: _c("33", t)
cyan   = lambda t: _c("36", t)
red    = lambda t: _c("31", t)
bold   = lambda t: _c("1",  t)


# ── Progress bar ──────────────────────────────────────────────────────────────

def _progress(done, total):
    if total <= 0:
        bar = "  downloading…"
    else:
        pct   = done / total
        width = 30
        filled = int(width * pct)
        bar = f"  [{'█' * filled}{'░' * (width - filled)}] {pct*100:5.1f}%  {done//1024}KB/{total//1024}KB"
    print(f"\r{bar}", end="", flush=True)


# ── Sub-commands ──────────────────────────────────────────────────────────────

def cmd_formats(_args):
    print(bold("\n  Audio formats:"))
    for k in sorted(AUDIO_FORMATS):
        t, fmt, q = AUDIO_FORMATS[k]
        print(f"    {cyan(k):<14}  {fmt.upper()} @ {q}")

    print(bold("\n  Video formats:"))
    for k in sorted(VIDEO_FORMATS):
        t, fmt, q = VIDEO_FORMATS[k]
        print(f"    {cyan(k):<14}  {fmt.upper()} {q}")

    print(bold("\n  Options:"))
    print(f"    {'--translated':<14}  Download dubbed/translated audio track (where available)")
    print()


def cmd_download(args):
    url       = args.url
    fmt       = args.format
    translated = args.translated
    output    = args.output

    # Validate format early
    try:
        kind, fmt_name, quality = resolve_format(fmt)
    except ValueError as e:
        print(red(f"\n  ✗ {e}\n"))
        sys.exit(1)

    label = f"{'🎵' if kind == 'audio' else '🎬'}  {fmt_name.upper()} {quality}"
    if translated:
        label += "  [translated]"

    print(f"\n{bold('  URL:')}    {url}")
    print(f"{bold('  Format:')} {cyan(label)}\n")

    # ── Step 1: submit job ────────────────────────────────────────────────────
    print(f"  {yellow('⏳')} Submitting to y2save…", flush=True)
    try:
        job_resp = start_job(url, fmt, translated)
    except Exception as e:
        print(red(f"\n  ✗ Failed to submit: {e}"))
        sys.exit(1)

    status_url = job_resp.get("statusUrl") or job_resp.get("status_url")
    if status_url:
        job_id = status_url.rstrip("/").split("/")[-1]
    else:
        job_id = job_resp.get("id") or job_resp.get("jobId") or job_resp.get("job_id")
    if not job_id:
        print(red(f"\n  ✗ No job ID in response: {job_resp}"))
        sys.exit(1)

    print(f"  {green('✔')} Job accepted  {cyan(job_id)}\n")

    # ── Step 2: poll status ───────────────────────────────────────────────────
    print(f"  {yellow('⏳')} Processing", end="", flush=True)
    try:
        status = poll_status(job_id, interval=3.0, timeout=300.0)
    except TimeoutError as e:
        print(red(f"\n\n  ✗ {e}"))
        sys.exit(1)
    except RuntimeError as e:
        print(red(f"\n\n  ✗ {e}"))
        sys.exit(1)
    except Exception as e:
        print(red(f"\n\n  ✗ Error polling status: {e}"))
        sys.exit(1)

    print(f"\r  {green('✔')} Processing done\n")

    # ── Step 3: resolve download URL ──────────────────────────────────────────
    dl_url = (
        status.get("download_url")
        or status.get("downloadUrl")
        or status.get("url")
        or status.get("fileUrl")
    )
    if not dl_url:
        print(red(f"\n  ✗ No download URL in status response: {status}"))
        sys.exit(1)

    # ── Step 4: determine filename ────────────────────────────────────────────
    if output:
        dest = output
    else:
        server_name = (
            status.get("filename")
            or status.get("title")
            or dl_url.split("/")[-1].split("?")[0]
            or f"download.{fmt_name}"
        )
        dest = os.path.join(os.getcwd(), server_name)

    # ── Step 5: download file ─────────────────────────────────────────────────
    print(f"  {yellow('⬇')} Downloading → {cyan(dest)}")
    try:
        download_file(dl_url, dest, progress_cb=_progress)
    except Exception as e:
        print(red(f"\n\n  ✗ Download failed: {e}"))
        sys.exit(1)

    size_mb = os.path.getsize(dest) / (1024 * 1024)
    print(f"\n\n  {green('✔')} Saved  {bold(dest)}  ({size_mb:.2f} MB)\n")


# ── Argument parser ───────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="ytdl",
        description="Download audio/video via y2save.com",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd")

    # formats sub-command
    sub.add_parser("formats", help="List all available formats")

    # download sub-command (also the default)
    dl = sub.add_parser("download", help="Download a URL")
    dl.add_argument("url",  help="YouTube (or supported site) URL")
    dl.add_argument("-f", "--format",     default="mp4-720",
                    help="Format key, e.g. mp3-320, mp4-1080, flac (default: mp4-720)")
    dl.add_argument("-t", "--translated", action="store_true",
                    help="Download dubbed/translated audio track where available")
    dl.add_argument("-o", "--output",     default=None,
                    help="Output file path (default: filename from server)")

    # Allow bare  ytdl <url>  without the 'download' keyword
    if len(sys.argv) >= 2 and sys.argv[1] not in ("formats", "download", "-h", "--help"):
        sys.argv.insert(1, "download")

    args = parser.parse_args()

    if args.cmd == "formats":
        cmd_formats(args)
    elif args.cmd == "download":
        cmd_download(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
