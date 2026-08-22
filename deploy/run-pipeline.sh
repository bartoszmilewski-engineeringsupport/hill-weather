#!/usr/bin/env bash
# Hill Weather pipeline - one cron entry does everything.
#
# Twice a day, not four times: Open-Meteo weights API calls by variable count
# and location count, so a 496-hill build is worth thousands of weighted calls
# against a 10,000/day free-tier limit. Two runs is comfortable; four is not.
#
# Install on the VPS:
#   sudo cp deploy/run-pipeline.sh /opt/hillweather/deploy/
#   sudo chmod +x /opt/hillweather/deploy/run-pipeline.sh
#   crontab -e
#     15 5,16 * * *  /opt/hillweather/deploy/run-pipeline.sh >> /var/log/hillweather.log 2>&1
#
# 05:15 lands before anyone checks over breakfast; 16:15 catches the afternoon
# model run before people plan the next day.

set -euo pipefail

ROOT="${HILLWEATHER_ROOT:-/opt/hillweather}"
PYTHON="${PYTHON:-python3}"
cd "$ROOT"

log() { printf '%s  %s\n' "$(date -u '+%Y-%m-%d %H:%M:%SZ')" "$*"; }

log "pipeline start"

# 1. Archive the validation subset with the full variable set. This is the
#    record we score the forecast against later, and it cannot be refetched
#    after the fact - so it runs first and a failure here is worth shouting about.
if "$PYTHON" scripts/archive.py; then
    log "archive ok"
else
    log "ARCHIVE FAILED - validation data lost for this run"
fi

# 2. Build the live site from a fresh fetch of all 496 hills.
#    Written to a temp dir first so a half-finished build is never served.
STAGING="$(mktemp -d)"
trap 'rm -rf "$STAGING"' EXIT

if "$PYTHON" scripts/build.py --out "$STAGING"; then
    # Swap in atomically-ish: rsync --delete into the live docroot only after
    # the build has fully succeeded.
    rsync -a --delete "$STAGING/" "$ROOT/web/data/"
    log "build ok -> web/data"
else
    log "BUILD FAILED - keeping previous forecast in place"
    exit 1
fi

# 3. Weekly: push the raw archive to the NAS so it lands inside Restic backups.
if [ "$(date -u +%u)" = "7" ]; then
    if rsync -a --delete "$ROOT/archive/" "${NAS_ARCHIVE:-/mnt/nas/hillweather/archive/}"; then
        log "archive synced to NAS"
    else
        log "NAS sync failed (non-fatal)"
    fi
fi

log "pipeline done"
