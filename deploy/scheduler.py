#!/usr/bin/env python3
"""
Scheduler. Runs inside the compose stack so the schedule travels with the app.

Host cron was the obvious choice and the wrong one: it lives outside the repo,
has to be recreated by hand on every new machine, and fails silently if you
forget. Keeping it here means `docker compose up -d` on any host gives you the
whole system, web server and schedule together, with nothing to remember.

Standard library only, same as the rest of the project, so the container is
plain python:alpine with no build step and nothing to install.

Config comes from the environment (see .env.example):
    RUN_TIMES       comma separated HH:MM in UTC, default "05:15,16:15"
    RUN_ON_START    run once at startup if there is no forecast yet
    HEARTBEAT_URL   optional Uptime Kuma push URL, pinged after each run
    ROOT            project root inside the container
"""

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(os.environ.get("ROOT", "/app"))
RUN_TIMES = [t.strip() for t in
             os.environ.get("RUN_TIMES", "05:15,16:15").split(",") if t.strip()]
RUN_ON_START = os.environ.get("RUN_ON_START", "1") not in ("0", "false", "no")
HEARTBEAT_URL = os.environ.get("HEARTBEAT_URL", "").strip()
PYTHON = sys.executable

DATA = ROOT / "web" / "data"
STAGING = ROOT / "web" / ".data-staging"
STATUS = DATA / "_status.json"


def log(msg):
    print(f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M:%SZ}  {msg}", flush=True)


def run(script, *args):
    """Run one pipeline script, streaming its output into our own log.

    Streamed line by line rather than captured and printed at the end. A build
    can legitimately sit in a rate-limit backoff for twenty minutes, and a job
    that pauses that long while showing nothing is indistinguishable from a
    hung one. Anyone watching the log deserves to see the backoff happening.
    """
    cmd = [PYTHON, "-u", str(ROOT / "scripts" / script), *args]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    tail = []
    for line in proc.stdout:
        line = line.rstrip()
        if line:
            log(f"  {line}")
            tail.append(line)
            del tail[:-8]
    code = proc.wait()
    if code != 0 and tail:
        log(f"  ! exited {code}")
    return code == 0


def write_status(ok, detail):
    """Heartbeat file. Uptime Kuma keyword-checks this, so monitoring works the
    same on any host without reconfiguring anything."""
    DATA.mkdir(parents=True, exist_ok=True)
    STATUS.write_text(json.dumps({
        "ok": ok,
        "detail": detail,
        "last_run_utc": datetime.now(timezone.utc).replace(
            microsecond=0).isoformat(),
        "run_times_utc": RUN_TIMES,
    }, indent=2), encoding="utf-8")


def heartbeat(ok, msg):
    """Ping an Uptime Kuma push monitor, if one is configured.

    The status file alone is not enough to monitor this properly: if the
    scheduler dies, the file sits there still saying everything is fine while
    the forecast quietly goes stale. A push monitor inverts that. Silence is
    the alert, so a dead container, a hung process or a broken network all get
    caught by the same check.

    Never allowed to break the pipeline. Monitoring that can take down the
    thing it monitors is worse than no monitoring.
    """
    if not HEARTBEAT_URL:
        return
    try:
        # Two conventions, because the sensible host for this depends on where
        # the stack is running. Uptime Kuma takes query parameters, but it has
        # to be reachable inbound. healthchecks.io wants a bare GET for success
        # and /fail for failure, and needs no inbound access at all, which is
        # what you want when the monitoring lives on a LAN behind the VPS.
        if "hc-ping.com" in HEARTBEAT_URL or "healthchecks" in HEARTBEAT_URL:
            url = HEARTBEAT_URL if ok else HEARTBEAT_URL.rstrip("/") + "/fail"
            data = msg.encode()[:10000]           # shows up in the ping log
        else:
            sep = "&" if "?" in HEARTBEAT_URL else "?"
            url = (f"{HEARTBEAT_URL}{sep}status={'up' if ok else 'down'}"
                   f"&msg={urllib.parse.quote(msg)}")
            data = None
        with urllib.request.urlopen(url, data=data, timeout=15):
            pass
        log("heartbeat sent")
    except Exception as e:                        # noqa: BLE001
        log(f"heartbeat failed, ignoring: {e}")


def pipeline():
    log("pipeline start")

    # Archive first. It cannot be refetched after the fact, so a failure here
    # is worse than a stale website and is logged loudly.
    if run("archive.py"):
        log("archive ok")
    else:
        log("ARCHIVE FAILED, validation data lost for this run")

    # Build into staging so a half-finished build is never served.
    if STAGING.exists():
        shutil.rmtree(STAGING, ignore_errors=True)
    if not run("build.py", "--out", str(STAGING)):
        log("BUILD FAILED, keeping the previous forecast in place")
        write_status(False, "build failed, serving previous forecast")
        heartbeat(False, "build failed")
        shutil.rmtree(STAGING, ignore_errors=True)
        return False

    # Swap. Same filesystem, so this is a rename and the window where the site
    # has no data is a few milliseconds.
    old = ROOT / "web" / ".data-old"
    shutil.rmtree(old, ignore_errors=True)
    if DATA.exists():
        DATA.rename(old)
    STAGING.rename(DATA)
    shutil.rmtree(old, ignore_errors=True)

    log("build ok, swapped into web/data")

    # The link preview reports the day it was built for, so it is regenerated
    # after the swap, from the data now being served.
    #
    # This needs Pillow and a serif font, neither of which is in the stock
    # python:3.12-alpine image, so out of the box it skips and the committed
    # card stays. That is deliberate: the card carries its own date, so a stale
    # preview is out of date but never wrong about the day it describes, and a
    # nice-to-have is not worth risking the build over. To turn it on, see
    # "Day-specific link preview" in docs/RUNBOOK.md.
    if not run("og_image.py"):
        log("link preview not regenerated, keeping the previous one")

    write_status(True, "ok")
    heartbeat(True, "build ok")
    return True


def next_run():
    now = datetime.now(timezone.utc)
    candidates = []
    for t in RUN_TIMES:
        try:
            hh, mm = (int(x) for x in t.split(":"))
        except ValueError:
            log(f"ignoring bad RUN_TIMES entry {t!r}")
            continue
        today = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
        candidates += [today, today + timedelta(days=1)]
    future = sorted(c for c in candidates if c > now)
    return future[0] if future else now + timedelta(hours=1)


def main():
    # `--once` runs the pipeline immediately and exits. Same code path as the
    # scheduled run, so a manual rebuild can never behave differently from an
    # automatic one.
    if "--once" in sys.argv:
        sys.exit(0 if pipeline() else 1)

    log(f"scheduler up. runs at {', '.join(RUN_TIMES)} UTC. root={ROOT}")

    if RUN_ON_START and not (DATA / "index.json").exists():
        log("no forecast present, building immediately")
        pipeline()

    while True:
        nxt = next_run()
        wait = (nxt - datetime.now(timezone.utc)).total_seconds()
        log(f"next run {nxt:%Y-%m-%d %H:%M}Z, sleeping {wait / 3600:.1f}h")
        # Wake periodically rather than one long sleep, so a container that is
        # paused or a host that suspends does not overshoot the slot.
        while wait > 0:
            time.sleep(min(wait, 300))
            wait = (nxt - datetime.now(timezone.utc)).total_seconds()
        pipeline()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("scheduler stopping")
