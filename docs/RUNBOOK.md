# Runbook

Everything needed to stand this up on a new host, and everything that lives
outside the repo and would otherwise be tribal knowledge.

The design goal: **the only host-specific thing is `deploy/.env`.** Code comes
from git, the forecast rebuilds itself, and the schedule lives inside the
compose stack. Moving hosts is a config change, not a code change.

---

## What actually has to move

| Thing | Moves how | Replaceable? |
|---|---|---|
| Code | `git clone` | Yes, trivially |
| Forecast data | Rebuilds within minutes on first start | Yes |
| **Archive** | `migrate.sh export` / `import` | **No. This is the only irreplaceable state.** |
| Host config | `deploy/.env` | Yes, but easier to carry it across |
| DNS, TLS, proxy host | Manual, see below | Yes |

The archive is raw forecast history used to score the algorithm. It cannot be
refetched after the fact, so it is the one thing worth being careful about.

---

## Fresh install on any host

Needs Docker and Docker Compose. Nothing else: no Python on the host, no pip,
no build step. Both containers are stock images.

```bash
git clone https://github.com/bartoszmilewski-engineeringsupport/hill-weather.git /opt/hillweather
```

```bash
cd /opt/hillweather/deploy && cp .env.example .env
```

Edit `.env`. On a new VPS usually only `PROJECT_ROOT` and `WEB_PORT` change.
On the homelab, point `ARCHIVE_DIR` straight at the NAS mount and skip the
sync step entirely.

```bash
cd /opt/hillweather/deploy && docker compose up -d
```

The scheduler builds immediately when there is no forecast present, so the site
is live within about ten minutes rather than waiting for the next slot.

```bash
docker compose logs -f scheduler
```

---

## Moving to a different host

On the old host:

```bash
cd /opt/hillweather/deploy && ./migrate.sh export
```

Copy the tarball across, then on the new host do the fresh install above, but
import instead of copying `.env.example`:

```bash
cd /opt/hillweather/deploy && ./migrate.sh import /tmp/hillweather-state-2026-08-22.tar.gz
```

```bash
cd /opt/hillweather/deploy && docker compose up -d && ./migrate.sh verify
```

`verify` checks the archive came across intact, `.env` exists, and the site is
serving. Do not decommission the old host until it passes.

Then repoint DNS and add the proxy host. Keep the old host running until DNS
has propagated; there is no database, so both can serve simultaneously with no
risk of divergence.

---

## The parts that live outside the repo

### DNS

Both domains are registered and served by Cloudflare, so there is no
nameserver change to make. Add four A records, all pointing at the host:

```
A    hillweather.co.uk        <host-ip>     DNS only
A    www.hillweather.co.uk    <host-ip>     DNS only
A    hillweather.uk           <host-ip>     DNS only
A    www.hillweather.uk       <host-ip>     DNS only
```

**Create them unproxied (grey cloud).** With the orange cloud on, Cloudflare
answers with its own addresses, so a certificate failure gives you no way to
tell whether the problem is the host, the proxy host, or Cloudflare. Get it
working end to end first, then turn the proxy on.

Must resolve before requesting a certificate.

### Nginx Proxy Manager

- Proxy host: `hillweather.co.uk`, `www.hillweather.co.uk` to
  `http://<host-ip>:<WEB_PORT>`. Request a Let's Encrypt certificate. Enable
  Block Common Exploits; leave Websockets off.
- Second entry: `hillweather.uk` and `www.hillweather.uk` as a **301 redirect**
  to `https://hillweather.co.uk`, with its own certificate.

Known trap: NPM has a latent trailing-space bug on the forward hostname field.
If you get 502s straight after editing a proxy host in the UI, check for a
stray space before assuming the container is broken.

### Cloudflare

Add it **only after HTTPS already works direct to the host**, otherwise
diagnosing certificate problems becomes guesswork.

1. Move nameservers to Cloudflare.
2. Set SSL mode to **Full (strict)** before enabling the proxy. Flexible mode
   against a host that already has a valid certificate causes redirect loops,
   which is the most common way this goes wrong.
3. Then turn on the orange cloud.

Cloudflare matters here because traffic is spiky by design: the growth model is
someone sharing a screenshot in a walking group on a Friday night. The JSON is
static and cacheable, so the edge absorbs it.

### Monitoring

Two monitors in Uptime Kuma, because they catch different things.

**1. Dead man's switch (the important one).**

The scheduler pings a URL after every run, up on success and down on failure.
Silence is the alert, so one check catches a failed build, a dead container, a
hung process and a broken network.

Use **healthchecks.io** rather than Uptime Kuma for this. Kuma lives on the
homelab and is deliberately LAN only, so a push monitor would mean exposing the
dashboard that lists the entire homelab to the internet in order to receive one
heartbeat. healthchecks.io is free and the VPS only makes an outbound call, so
nothing gets exposed.

- Create a check: period `12 hours`, grace `2 hours`.
- Put its ping URL in `HEARTBEAT_URL` in `deploy/.env`.
- `docker compose up -d` to pick it up.

If the stack ever moves onto the homelab, where Kuma is reachable, a Kuma push
monitor works too and the scheduler detects which style to use from the URL.

**2. Keyword monitor (site availability).**

- Type: HTTP(s) - Keyword
- URL: `https://hillweather.co.uk/data/_status.json`
- Keyword: `"ok": true`
- Heartbeat Interval: 3600

This one tells you the site is reachable and serving. On its own it is not
enough: if the scheduler dies, the last forecast keeps being served and this
monitor stays green while the data quietly goes stale. That is what the push
monitor is for.

### After changing CSS or JavaScript

```bash
python3 scripts/version_assets.py
```

Then commit the rewritten pages along with the asset. This stamps a content
hash onto the URL, so a changed file is a changed URL and no cache anywhere can
serve the old one against new markup.

That failure is worth understanding, because it looks exactly like a code bug:
new HTML arrives, the stylesheet is still the cached previous version, and the
site renders with giant icons, unstyled controls and a broken layout while the
origin is entirely correct throughout.

The usual advice is to set Cloudflare's Browser Cache TTL to "Respect Existing
Headers", but that option is not on every plan. Versioned URLs need no
cooperation from the CDN, the browser or a dashboard toggle.

### Descriptions and route links

`data/sources.json` holds a Wikipedia extract and a Walkhighlands link per
hill, committed so the twice-daily build never touches either site. Refresh it
only when the hill list changes:

```bash
python3 scripts/sources.py            # fill in anything missing
python3 scripts/sources.py --status   # coverage
```

Two rules the script exists to enforce. Wikipedia is matched by proximity AND
name, never proximity alone, because nearest-article-wins silently returns
Walla Crag for Bleaberry Fell and a description of the wrong mountain is worse
than none. Walkhighlands is linked only, never copied, and every slug is
verified with a HEAD request so a broken link is never published.

### Contact form

The one part of the site that is a running service rather than a file, because
a static page cannot send email. It lives in the same compose stack, is reached
through nginx at `/api/`, and can only ever send to one fixed address, so it
cannot be turned into an open relay.

**1. Create the address.** Cloudflare Email Routing (free, on the domain
already there): add `contact@hillweather.co.uk` and forward it to a real
mailbox.

**2. Relay through an account with a sending reputation.** A VPS IP has none,
so mail sent straight from the box goes to spam. Gmail needs an app password,
not the account password.

**3. Configure it** in `deploy/.env`:

```
CONTACT_TO=you@example.com
CONTACT_FROM=you@gmail.com
SMTP_USER=you@gmail.com
SMTP_PASS=your-16-character-app-password
FORM_SECRET=<python3 -c "import secrets;print(secrets.token_hex(32))">
```

With `CONTACT_TO` unset the form refuses to send and says so, rather than
failing confusingly.

```bash
cd /opt/hillweather/deploy && docker compose up -d
```

```bash
curl -s https://hillweather.co.uk/api/contact/health
```

`{"ok": true, "to": true}` means it is configured and running.

**Spam handling**, in layers, because a public form on an indexed site gets
found within weeks:

| Layer | What it stops |
|---|---|
| Signed token the page must fetch first | Bots that POST blind. Does most of the work. |
| Three second minimum age on that token | Scripts that fill and submit instantly |
| Honeypot field | Form-fillers. Accepted and discarded, so the bot learns nothing. |
| 3 messages per IP per hour | Floods |
| Header sanitising and a strict address check | Header injection, which is how contact forms become spam relays |

If it is ever overwhelmed, Cloudflare Turnstile is the next layer and is free.

### Archive backup

On the VPS, a weekly pull from the NAS side keeps the archive inside the
existing Restic backups:

```bash
rsync -az --delete root@<vps>:/opt/hillweather/archive/ /mnt/nas/hillweather/archive/
```

On the homelab this is unnecessary: set `ARCHIVE_DIR` to the NAS path directly.

---

## Routine operations

Rebuild now, without waiting for a slot. Run it DETACHED: a build can sit in a
rate-limit backoff for twenty minutes or more, and `exec` without `-d` dies if
the SSH session drops.

```bash
cd /opt/hillweather/deploy && docker compose exec -d scheduler sh -c 'python3 /app/deploy/scheduler.py --once > /app/web/.once.log 2>&1'
```

```bash
tail -f /opt/hillweather/web/.once.log
```

**Then purge the Cloudflare cache**, or the site keeps serving the old
forecast for up to thirty minutes and it looks like the build failed.

The same trap catches CSS and JS changes. Cloudflare applies its own multi-hour
default to those extensions unless told otherwise, so a stylesheet change
shipped alongside new markup left the site serving four-hour-old styles against
a new page: giant icons, unstyled controls, a broken layout that looked like a
code bug and was not. `nginx.conf` now sets five minutes on CSS and JS, but
purge anyway if you want a change visible immediately:

Cloudflare, hillweather.co.uk, Caching, Configuration, Purge Everything.

Only needed after a MANUAL rebuild. The scheduled 05:15 and 16:15 runs are far
enough apart that the cache expires on its own.

Confirm a build is genuinely working rather than hung:

```bash
cd /opt/hillweather/deploy && docker compose exec scheduler ps -o pid,etime,args
```

A child process running `archive.py` or `build.py` means it is fetching or
waiting out a backoff. Leave it: the backoff is deliberate, and failing would
leave the site stale until the next slot.

**Do not stack manual builds.** Three inside twenty minutes exhausted the
hourly API budget and every build after that failed for an hour. If a rebuild
is fighting the limit, the 05:15 run will do it with a fresh budget.

Update after a `git push` from the laptop or desktop:

```bash
cd /opt/hillweather && git pull && docker compose -f deploy/docker-compose.yml restart scheduler
```

The web container serves files straight off disk, so HTML, CSS and data changes
need no restart at all.

**`nginx.conf` is the exception.** nginx reads its config once at startup, so
editing the file changes nothing until the container is recreated. `up -d`
alone will NOT do it: compose sees an unchanged service definition and leaves
the container running.

```bash
cd /opt/hillweather/deploy && docker compose up -d --force-recreate web
```

Then check it actually came back, because nginx resolves upstream hostnames at
startup and will refuse to start if one is missing:

```bash
cd /opt/hillweather/deploy && docker compose ps web && docker compose logs --tail 15 web
```

How much history exists:

```bash
docker compose exec scheduler python3 /app/scripts/archive.py --status
```

---

## Day-specific link preview

`scripts/og_image.py` draws `web/og.png`, the image that appears when the site
is pasted into WhatsApp, Slack or a forum. It reads the built forecast and
reports the actual day: "Above the cloud. 241 of 282 tops stand clear", rather
than a fixed logo. Pasting the link into a walking group is the whole growth
model, so this is worth more than it looks.

The scheduler calls it after every successful build, but the stock
`python:3.12-alpine` image has neither Pillow nor a serif font, so by default
the step skips and the committed card stays in place. The log says
`link preview not regenerated, keeping the previous one`. Nothing else is
affected, and the card carries its own date, so a stale preview is out of date
but never wrong about which day it describes.

To turn it on, give the scheduler container the two things it needs:

```yaml
  scheduler:
    image: python:3.12-alpine
    command: ["sh", "-c",
              "apk add --no-cache font-dejavu >/dev/null &&
               pip install --no-cache-dir --quiet pillow &&
               exec python3 /app/deploy/scheduler.py"]
```

Then recreate it. Remember that a changed command needs `--force-recreate`,
because compose leaves a container alone when only its config text moved:

```bash
docker compose up -d --force-recreate scheduler
```

This adds a network fetch to every container start. If that is not wanted, the
alternative is to run the script by hand after a design change and commit the
result, which is how the card was maintained before:

```bash
python scripts/og_image.py
```

One caveat either way. Link scrapers cache the preview hard, and the URL stays
`/og.png` on purpose, so a link already shared will keep showing whatever
Facebook or WhatsApp fetched the first time. Giving the file a versioned URL
would fix that and break every previously shared link instead, which is the
worse trade.

---

## Working from two machines

Laptop and desktop both clone from GitHub. Generated data and the archive are
gitignored, so there is nothing to conflict over: pull, edit, push.

Only the host running the stack has an archive, and that is deliberate. Do not
try to sync it between development machines.
