#!/usr/bin/env bash
# Move Hill Weather between hosts.
#
# The code comes from git and the forecast rebuilds itself, so only two things
# actually need moving: the archive, which cannot be refetched, and .env, which
# holds the host configuration.
#
#   ./migrate.sh export                 -> hillweather-state-YYYY-MM-DD.tar.gz
#   ./migrate.sh import <file.tar.gz>   restore onto a new host
#   ./migrate.sh verify                 sanity check before you decommission
#
# Full migration to a new VPS or onto the homelab:
#
#   old host:  cd /opt/hillweather/deploy && ./migrate.sh export
#              scp hillweather-state-*.tar.gz newhost:/tmp/
#   new host:  git clone https://github.com/bartoszmilewski-engineeringsupport/hill-weather.git /opt/hillweather
#              cd /opt/hillweather/deploy
#              ./migrate.sh import /tmp/hillweather-state-*.tar.gz
#              edit .env if paths or the port differ on this machine
#              docker compose up -d
#   then:      repoint DNS, add the proxy host, done.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(dirname "$HERE")"
cd "$ROOT"

# Read ARCHIVE_DIR from .env if present, otherwise assume the default location.
ARCHIVE_DIR="$ROOT/archive"
if [ -f "$HERE/.env" ]; then
    # shellcheck disable=SC1091
    set -a; . "$HERE/.env"; set +a
    ARCHIVE_DIR="${ARCHIVE_DIR:-$ROOT/archive}"
fi

case "${1:-}" in

export)
    OUT="hillweather-state-$(date -u +%Y-%m-%d).tar.gz"
    if [ ! -d "$ARCHIVE_DIR" ]; then
        echo "no archive at $ARCHIVE_DIR, nothing to export" >&2
        exit 1
    fi
    echo "archiving $ARCHIVE_DIR"
    tar czf "$OUT" \
        -C "$(dirname "$ARCHIVE_DIR")" "$(basename "$ARCHIVE_DIR")" \
        $([ -f "$HERE/.env" ] && echo "-C $HERE .env")
    echo
    echo "wrote $(pwd)/$OUT  ($(du -h "$OUT" | cut -f1))"
    echo "copy it to the new host, then run: ./migrate.sh import <file>"
    ;;

import)
    SRC="${2:-}"
    [ -f "$SRC" ] || { echo "usage: ./migrate.sh import <file.tar.gz>" >&2; exit 1; }
    echo "restoring from $SRC"
    tar xzf "$SRC" -C "$ROOT"
    # .env lands at the repo root from the tar; move it where compose expects it.
    [ -f "$ROOT/.env" ] && mv "$ROOT/.env" "$HERE/.env"
    [ -f "$HERE/.env" ] || cp "$HERE/.env.example" "$HERE/.env"
    echo
    echo "restored. now:"
    echo "  1. check deploy/.env  (PROJECT_ROOT, ARCHIVE_DIR, WEB_PORT)"
    echo "  2. docker compose up -d"
    echo "  3. ./migrate.sh verify"
    ;;

verify)
    fail=0
    echo "checking this host"

    if [ -d "$ARCHIVE_DIR" ]; then
        runs=$(find "$ARCHIVE_DIR" -name '*.json.gz' | wc -l)
        days=$(find "$ARCHIVE_DIR" -name '*.json.gz' -printf '%f\n' 2>/dev/null \
               | cut -c1-10 | sort -u | wc -l)
        echo "  archive      $runs runs across $days days"
        [ "$runs" -gt 0 ] || { echo "  archive is EMPTY, did the export include it?"; fail=1; }
    else
        echo "  archive      MISSING at $ARCHIVE_DIR"; fail=1
    fi

    [ -f "$HERE/.env" ] && echo "  .env         present" \
                        || { echo "  .env         MISSING"; fail=1; }

    port="${WEB_PORT:-5003}"
    if curl -fsS "http://localhost:$port/data/_status.json" >/dev/null 2>&1; then
        echo "  web          serving on :$port"
        curl -fsS "http://localhost:$port/data/_status.json" | sed 's/^/               /'
    else
        echo "  web          not responding on :$port (is the stack up?)"; fail=1
    fi

    echo
    [ "$fail" -eq 0 ] && echo "all good, safe to decommission the old host" \
                      || echo "problems above, do NOT decommission yet"
    exit "$fail"
    ;;

*)
    sed -n '2,25p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
