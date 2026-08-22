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

```
A    hillweather.uk       <host-ip>
A    www.hillweather.uk   <host-ip>
A    hillweather.co.uk    <host-ip>
```

Must resolve before requesting a certificate.

### Nginx Proxy Manager

- Proxy host: `hillweather.uk`, `www.hillweather.uk` to `http://<host-ip>:<WEB_PORT>`.
  Request a Let's Encrypt certificate. Enable Block Common Exploits and
  Websockets off.
- Second entry: `hillweather.co.uk` as a **301 redirect** to
  `https://hillweather.uk`, with its own certificate.

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

Uptime Kuma, HTTP keyword monitor:

- URL: `https://hillweather.uk/data/_status.json`
- Keyword: `"ok": true`

The scheduler writes that file after every run, so this catches a build that
has silently stopped refreshing, which a plain uptime check would not.

### Archive backup

On the VPS, a weekly pull from the NAS side keeps the archive inside the
existing Restic backups:

```bash
rsync -az --delete root@<vps>:/opt/hillweather/archive/ /mnt/nas/hillweather/archive/
```

On the homelab this is unnecessary: set `ARCHIVE_DIR` to the NAS path directly.

---

## Routine operations

Rebuild now, without waiting for a slot:

```bash
docker compose exec scheduler python3 /app/deploy/scheduler.py --once
```

Update after a `git push` from the laptop or desktop:

```bash
cd /opt/hillweather && git pull && docker compose -f deploy/docker-compose.yml restart scheduler
```

The web container serves files straight off disk, so it only needs restarting
if `nginx.conf` changed.

How much history exists:

```bash
docker compose exec scheduler python3 /app/scripts/archive.py --status
```

---

## Working from two machines

Laptop and desktop both clone from GitHub. Generated data and the archive are
gitignored, so there is nothing to conflict over: pull, edit, push.

Only the host running the stack has an archive, and that is deliberate. Do not
try to sync it between development machines.
