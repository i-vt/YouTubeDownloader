# getsave-cli

Dockerized CLI that downloads videos via the **get-save.com** service. Built from a HAR capture of the site's request flow.

> ⚠️ You stated you have rights to the content you'll download with this. Don't use it to grab third-party copyrighted videos — that's a TOS violation on YouTube's end and likely infringement on the rights-holder's end.

## How it works

The site's front-end JS does roughly this:

1. POSTs `{ "url": "<source>" }` to `https://api.get-save.com/api/v1/vidinfo` (falls back to `api-cdn.get-save.com` on failure).
2. Receives a JSON blob with `meta.title`, `meta.thumbnail`, and a `sizes` array of format entries (`protocol`, `ext`, `height`, `acodec`, `filesize`, `url`).
3. Filters out audio-only and unsupported protocols, picks the entry closest to the requested height, and downloads it.
4. **For YouTube only**, it rewrites the file URL through `https://proxy.get-save.com/` and appends a `&title=...[get.gt]` parameter so the proxy sets the right `Content-Disposition`. Other hosts use the direct URL.

This CLI replicates that flow. The ad/popup machinery on the website is skipped — we go straight from the API response to the file download.

## Build

```bash
docker build -t getsave-cli .
```

## Use

```bash
# Download at 1080p (default) to ./downloads
docker run --rm -v "$PWD/downloads:/downloads" getsave-cli \
  "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Pick a specific quality (closest match wins)
docker run --rm -v "$PWD/downloads:/downloads" getsave-cli \
  -q 720 "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# List available formats without downloading
docker run --rm getsave-cli -l "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# Dump the raw API response (useful for debugging unsupported sites)
docker run --rm getsave-cli --json "https://example.com/video"

# Override the output filename
docker run --rm -v "$PWD/downloads:/downloads" getsave-cli \
  --filename "my-clip" "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

### Quality argument

Pass `-q <height>` where `<height>` is one of `144 240 360 480 720 1080 1440 2160 4320`. Anything else gets snapped to the closest available format (preferring lower over higher, matching the site's behavior).

## Supported sites

The site advertises support for YouTube, VK, Yandex, RuTube, Telegram, Odnoklassniki, Mail.ru video, Dzen, Smotrim, Pinterest, TikTok, Instagram, and several others. The CLI hits the same API, so anything the website can handle should work here. Private/age-gated/region-locked videos will fail with an empty `sizes` array.

## Exit codes

| Code | Meaning |
|------|---------|
| 0    | Success |
| 2    | API request failed (both endpoints) |
| 3    | API returned but had no downloadable formats |
| 4    | Quality selection failed |
| 5    | The download itself failed (network, 403, etc.) |

## Caveats

- The get-save proxy can rate-limit you, return 403, or just disappear — there's no SLA on a free third-party scraper.
- YouTube's tokenized URLs (`signature`, `expire`) are short-lived. Don't pause for an hour between fetching info and downloading.
- This isn't `yt-dlp`. If you need something maintained, that's the answer.
