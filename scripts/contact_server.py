#!/usr/bin/env python3
"""
Contact form handler.

A static site cannot send email, so this is the one piece of the project that
is a running service rather than a file. It stays deliberately small: standard
library only, no framework, no database, and it can only ever send to one fixed
address, so it can never be turned into an open relay.

    GET  /api/contact/token   issue a short-lived signed token
    POST /api/contact         validate, rate limit, relay by SMTP
    GET  /api/contact/health  liveness for the compose healthcheck

Spam handling, in layers, because a public form on an indexed site gets found
by bots within weeks:

  1. A signed token the page must fetch first. Bots that POST blind never have
     one. This is the layer that does most of the work.
  2. A minimum age on that token. A human cannot read the page, type a message
     and submit inside three seconds; a script does it instantly.
  3. A honeypot field. Hidden from people, irresistible to form-fillers. When
     it is filled we accept the request and silently discard it, so the bot
     learns nothing.
  4. Per-IP rate limiting.
  5. Hard length limits, and strict header sanitising.

Configuration comes from the environment; see deploy/.env.example.
"""

import hashlib
import hmac
import json
import os
import re
import smtplib
import sys
import time
from collections import defaultdict, deque
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("CONTACT_PORT", "5010"))
SECRET = os.environ.get("FORM_SECRET", "").encode() or os.urandom(32)
TO_ADDR = os.environ.get("CONTACT_TO", "")
FROM_ADDR = os.environ.get("CONTACT_FROM", TO_ADDR)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

TOKEN_MIN_AGE = 3          # seconds; below this it was not typed by a person
TOKEN_MAX_AGE = 3600       # an hour to write a message is plenty
RATE_LIMIT = 3             # messages per IP
RATE_WINDOW = 3600         # per hour
MAX_NAME = 120
MAX_EMAIL = 200
MAX_SUBJECT = 200
MAX_MESSAGE = 5000
MAX_BODY_BYTES = 16 * 1024

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")
_hits = defaultdict(deque)


def log(msg):
    print(f"{time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}  {msg}",
          flush=True)


def make_token():
    issued = str(int(time.time()))
    sig = hmac.new(SECRET, issued.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{issued}.{sig}"


def check_token(token):
    """Return None if good, or a reason string."""
    if not token or "." not in token:
        return "missing token"
    issued, sig = token.rsplit(".", 1)
    expected = hmac.new(SECRET, issued.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        return "bad token"
    try:
        age = time.time() - int(issued)
    except ValueError:
        return "bad token"
    if age < TOKEN_MIN_AGE:
        return "too fast"
    if age > TOKEN_MAX_AGE:
        return "token expired"
    return None


def rate_limited(ip):
    now = time.time()
    hits = _hits[ip]
    while hits and now - hits[0] > RATE_WINDOW:
        hits.popleft()
    if len(hits) >= RATE_LIMIT:
        return True
    hits.append(now)
    if len(_hits) > 10000:                     # keep the table bounded
        for k in [k for k, v in _hits.items() if not v][:5000]:
            _hits.pop(k, None)
    return False


def header_safe(value):
    """Strip anything that could inject a new header.

    Without this, a sender address containing a newline can add arbitrary
    headers to the outgoing message, which is how contact forms become spam
    relays.
    """
    return re.sub(r"[\r\n]+", " ", value or "").strip()


def send(name, email, subject, message, ip):
    msg = EmailMessage()
    msg["To"] = TO_ADDR
    msg["From"] = FROM_ADDR
    msg["Subject"] = f"[hillweather.co.uk] {header_safe(subject) or 'Contact form'}"
    # Reply-To only when the address is well formed, so hitting reply works but
    # a malformed address can never reach the header.
    if EMAIL_RE.match(email):
        msg["Reply-To"] = header_safe(email)
    msg.set_content(
        f"From:    {name}\n"
        f"Email:   {email}\n"
        f"IP:      {ip}\n"
        f"Sent:    {time.strftime('%Y-%m-%d %H:%M:%SZ', time.gmtime())}\n"
        f"\n{message}\n")

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=20) as s:
        s.starttls()
        if SMTP_USER:
            s.login(SMTP_USER, SMTP_PASS)
        s.send_message(msg)


class Handler(BaseHTTPRequestHandler):
    server_version = "hillweather-contact"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        pass                                    # we do our own logging

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def client_ip(self):
        # Only ever reached through our own nginx, which is in turn behind
        # Cloudflare, so these headers are set by us rather than the caller.
        return (self.headers.get("CF-Connecting-IP")
                or (self.headers.get("X-Forwarded-For") or "").split(",")[0].strip()
                or self.client_address[0])

    def do_GET(self):
        if self.path == "/api/contact/health":
            return self._json(200, {"ok": True, "to": bool(TO_ADDR)})
        if self.path == "/api/contact/token":
            return self._json(200, {"token": make_token()})
        return self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/contact":
            return self._json(404, {"error": "not found"})

        ip = self.client_ip()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return self._json(400, {"error": "bad request"})
        if length <= 0 or length > MAX_BODY_BYTES:
            return self._json(413, {"error": "message too large"})

        try:
            data = json.loads(self.rfile.read(length))
        except (ValueError, UnicodeDecodeError):
            return self._json(400, {"error": "bad request"})

        # Honeypot. Accept it so the bot learns nothing, then bin it.
        if (data.get("website") or "").strip():
            log(f"honeypot hit from {ip}")
            return self._json(200, {"ok": True})

        reason = check_token(data.get("token"))
        if reason:
            log(f"rejected from {ip}: {reason}")
            return self._json(400, {"error": "Please reload the page and try again."})

        if rate_limited(ip):
            log(f"rate limited {ip}")
            return self._json(429, {"error":
                "That is a few messages in a short time. Try again later."})

        name = (data.get("name") or "").strip()[:MAX_NAME]
        email = (data.get("email") or "").strip()[:MAX_EMAIL]
        subject = (data.get("subject") or "").strip()[:MAX_SUBJECT]
        message = (data.get("message") or "").strip()[:MAX_MESSAGE]

        if not name or not message:
            return self._json(400, {"error": "Please fill in your name and a message."})
        if not EMAIL_RE.match(email):
            return self._json(400, {"error": "That email address does not look right."})

        if not TO_ADDR:
            log("CONTACT_TO is not set; refusing to send")
            return self._json(503, {"error": "The contact form is not configured yet."})

        try:
            send(name, email, subject, message, ip)
        except Exception as e:                   # noqa: BLE001
            log(f"send failed for {ip}: {type(e).__name__}: {e}")
            return self._json(502, {"error":
                "The message could not be sent. Please email contact@hillweather.co.uk "
                "directly."})

        log(f"sent from {ip} <{email}>")
        return self._json(200, {"ok": True})


def main():
    if not TO_ADDR:
        log("warning: CONTACT_TO is unset, the form will refuse to send")
    if not os.environ.get("FORM_SECRET"):
        log("warning: FORM_SECRET is unset, using a random one "
            "(tokens will not survive a restart)")
    log(f"contact handler listening on :{PORT}, relaying via {SMTP_HOST}:{SMTP_PORT}")
    ThreadingHTTPServer(("", PORT), Handler).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
