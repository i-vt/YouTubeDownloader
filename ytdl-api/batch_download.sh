#!/usr/bin/env bash
# batch_download.sh — download every YouTube URL in youtube_links.txt as MP3-320
# Uses the ytdl-api Docker image built from this project.
#
# Usage:
#   ./batch_download.sh                          # reads ./youtube_links.txt
#   ./batch_download.sh /path/to/links.txt       # custom file
#   WORKERS=5 ./batch_download.sh                # parallel downloads (default 3)

set -euo pipefail

LINKS_FILE="${1:-youtube_links.txt}"
OUTPUT_DIR="${OUTPUT_DIR:-./downloads}"
FORMAT="${FORMAT:-mp3-320}"
WORKERS="${WORKERS:-3}"
LOG_FILE="${OUTPUT_DIR}/download.log"
FAILED_FILE="${OUTPUT_DIR}/failed.txt"
DONE_FILE="${OUTPUT_DIR}/.done_urls"   # tracks already-downloaded URLs

# ── Colours ──────────────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

# ── Preflight ─────────────────────────────────────────────────────────────────
[[ ! -f "$LINKS_FILE" ]] && { echo -e "${RED}File not found: $LINKS_FILE${NC}"; exit 1; }
command -v docker &>/dev/null   || { echo -e "${RED}docker not found${NC}"; exit 1; }

mkdir -p "$OUTPUT_DIR"
touch "$LOG_FILE" "$FAILED_FILE" "$DONE_FILE"

# ── Extract valid YouTube URLs ────────────────────────────────────────────────
# Keeps only lines that start with http and contain youtube.com or youtu.be
mapfile -t ALL_URLS < <(
  grep -E '^https?://(www\.)?(youtube\.com/watch|youtu\.be/)' "$LINKS_FILE" || true
)

TOTAL=${#ALL_URLS[@]}
[[ $TOTAL -eq 0 ]] && { echo -e "${YELLOW}No YouTube URLs found in $LINKS_FILE${NC}"; exit 0; }

# Filter out already-done URLs
TODO=()
for url in "${ALL_URLS[@]}"; do
  grep -qxF "$url" "$DONE_FILE" || TODO+=("$url")
done

SKIPPED=$(( TOTAL - ${#TODO[@]} ))
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  File   : ${CYAN}$LINKS_FILE${NC}"
echo -e "  Format : ${CYAN}$FORMAT${NC}"
echo -e "  Output : ${CYAN}$OUTPUT_DIR${NC}"
echo -e "  Workers: ${CYAN}$WORKERS${NC}"
echo -e "  Total  : ${BOLD}$TOTAL${NC}  |  Skipped (done): ${BOLD}$SKIPPED${NC}  |  To download: ${BOLD}${#TODO[@]}${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo

[[ ${#TODO[@]} -eq 0 ]] && { echo -e "${GREEN}All URLs already downloaded.${NC}"; exit 0; }

# ── Worker function ───────────────────────────────────────────────────────────
ABS_OUTPUT="$(realpath "$OUTPUT_DIR")"
COUNTER=0
SUCCESS=0
FAIL=0
# Use a temp file for shared counters (subshells can't write to parent vars)
COUNT_FILE="$(mktemp)"
echo "0 0" > "$COUNT_FILE"   # success fail

_download_one() {
  local url="$1"
  local idx="$2"

  local result
  result=$(docker run --rm \
    -v "${ABS_OUTPUT}:/downloads" \
    ytdl-api \
    "$url" --format "$FORMAT" 2>&1)

  local exit_code=$?

  if echo "$result" | grep -q "✔ Saved"; then
    echo "$url" >> "$DONE_FILE"
    echo -e "  [${idx}/${TOTAL}] ${GREEN}✔${NC} $url" | tee -a "$LOG_FILE"
    # Thread-safe counter update
    flock "$COUNT_FILE" bash -c "
      read s f < '$COUNT_FILE'
      echo \$(( s + 1 )) \$f > '$COUNT_FILE'
    "
  else
    echo "$url" >> "$FAILED_FILE"
    echo -e "  [${idx}/${TOTAL}] ${RED}✗${NC} $url" | tee -a "$LOG_FILE"
    echo "    $(echo "$result" | grep -E '✗|error|Error' | head -1)" | tee -a "$LOG_FILE"
    flock "$COUNT_FILE" bash -c "
      read s f < '$COUNT_FILE'
      echo \$s \$(( f + 1 )) > '$COUNT_FILE'
    "
  fi
}

export -f _download_one
export ABS_OUTPUT FORMAT TOTAL LOG_FILE DONE_FILE FAILED_FILE COUNT_FILE

# ── Run with parallel workers ─────────────────────────────────────────────────
IDX=0
PIDS=()

for url in "${TODO[@]}"; do
  IDX=$(( IDX + 1 ))
  _download_one "$url" "$IDX" &
  PIDS+=($!)

  # Throttle: wait for a slot when we hit WORKERS limit
  if (( ${#PIDS[@]} >= WORKERS )); then
    wait "${PIDS[0]}"
    PIDS=("${PIDS[@]:1}")
  fi
done

# Wait for remaining
for pid in "${PIDS[@]}"; do
  wait "$pid"
done

# ── Summary ───────────────────────────────────────────────────────────────────
read SUCCESS FAIL < "$COUNT_FILE"
rm -f "$COUNT_FILE"

echo
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "  ${GREEN}✔ Downloaded : $SUCCESS${NC}"
echo -e "  ${RED}✗ Failed     : $FAIL${NC}"
[[ $SKIPPED -gt 0 ]] && echo -e "  ⏭  Skipped   : $SKIPPED (already done)"
echo -e "  Log          : $LOG_FILE"
[[ $FAIL -gt 0 ]] && echo -e "  Failed URLs  : ${RED}$FAILED_FILE${NC}"
echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo
