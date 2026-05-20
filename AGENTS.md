# Elbrus Cloud - agent notes

Marketing + lead-gen website for **Elbrus Cloud**, a cloud architecture &
cybersecurity consulting firm. Server-rendered Django app with one small
React island for the booking calendar.

This file captures the durable facts about how the project is laid out,
how it runs, and how it ships. Keep it current when those things change.

---

## Architecture

### Stack

- **Backend:** Django 5.1+ (server-rendered templates, classic MVC).
- **Database:** PostgreSQL 16 in production (Azure Database for PostgreSQL -
Flexible Server, private VNet access). SQLite is the default in local dev
when `DATABASE_URL` is unset.
- **Static / templates:** Django templates + Tailwind CSS 3 (standalone CLI).
WhiteNoise serves hashed static files in production via Gunicorn; Nginx
also has a direct `/static/` and `/media/` alias for hot-path assets.
- **Frontend island:** React 18 + Vite + TypeScript, mounted on
`/schedule/` only. The rest of the site is plain server-rendered HTML.
- **Email:** SMTP in prod, console backend in dev. Booking emails are
rendered from `backend/templates/scheduling/emails/`* (HTML + text twins).
- **iCal invites:** `icalendar` library; attached to confirmation /
reschedule / cancel mails.
- **SEO:** full server-side stack - `<title>`, meta description, canonical,
robots, OG, Twitter Card, JSON-LD (`Organization`, `WebSite`, `Article`,
`BreadcrumbList`, `LocalBusiness`, `Service`), `sitemap.xml` (via
`django.contrib.sitemaps`), `robots.txt` (via `django-robots`), RSS feed
for the blog.
- **Analytics / paid channels:** Google Tag Manager is the single source of
truth for ALL marketing tags in production. GA4, Google Ads, LinkedIn
Insight, Meta Pixel, Microsoft UET, and TikTok Pixel are configured INSIDE
the GTM container, not as separate `<script>` tags in this repo. Direct
GA4 is supported as a fallback for environments that don't run GTM.
Google Consent Mode v2 is wired in front of every tag with a default-deny
posture (the `partials/_consent_banner.html` updates state on user
acceptance). Every tag is gated on its env var being set: a deploy that
forgets to set `GTM_CONTAINER_ID` emits ZERO third-party requests.
The GTM container itself is versioned in this repo at
`infra/gtm/elbruscloud-container-v1.json`. Treat that file as the source
of truth: when you change something in the GTM UI, export the container
and overwrite the JSON; when you need to provision a fresh container,
import the JSON via Admin -> Import Container (Merge + Overwrite). See
`infra/gtm/README.md` for the full import workflow.
- **Attribution:** `core.middleware.AttributionMiddleware` captures the UTM
5-tuple plus paid-channel click IDs (`gclid`, `gbraid`, `wbraid`, `fbclid`,
`li_fat_id`, `msclkid`, `ttclid`) into HttpOnly first/last-touch cookies.
Views call `core.attribution.get_attribution_snapshot(request)` to persist
the merged snapshot to the `attribution` JSONField on `ContactMessage`,
`BookingInquiry`, and `Booking`. This enables offline conversion uploads
from converted bookings back to Google Ads / Meta / LinkedIn / etc.
- **Security (prod):** HTTPS-only redirect, HSTS, secure + SameSite=Strict
 cookies, `X-Forwarded-Proto` proxy header trust, `X-Frame-Options: DENY`,
 `nosniff`, strict referrer policy, Content-Security-Policy (per-request
 nonce + vendor allow-list for GTM/GA4/Google Ads/LinkedIn/Meta/Microsoft
 UET/TikTok), Permissions-Policy, Cross-Origin-Opener-Policy, and
 Cross-Origin-Resource-Policy (the last four emitted from
 `core.middleware.SecurityHeadersMiddleware`).
 Public POST endpoints (contact form, newsletter, booking inquiry / create /
 cancel) are rate-limited via `django-ratelimit`; the Django admin is
 protected against brute-force logins via `django-axes` (5 failures per
 IP+username -> 1h lockout). Nginx adds a 10 r/s pool (burst 20) on the
 application location, blocks dotfiles / sensitive extensions, and limits
 `/static/` + `/media/` to GET/HEAD. The Gunicorn systemd unit is
 sandboxed (`ProtectSystem=strict`, `NoNewPrivileges`, restricted syscalls,
 zeroed capability bounding set).
- **Errors (optional):** Sentry via `SENTRY_DSN` (loaded only if set).

### Repo layout

```
backend/                         Django project + apps
  manage.py
  elbrus/
    settings/{base,dev,prod}.py  DJANGO_SETTINGS_MODULE picks one
    urls.py, wsgi.py, asgi.py
  apps/                          (sys.path-injected, imported by short name)
    core/        SEO mixins, JSON-LD schema helpers, sitemaps, base views,
                 site context processor, `seed` management command, smoke
                 tests for SEO tags.
    pages/       Home, About, Services, Contact landing. `Service` model.
    blog/        Posts, RSS feed, sitemap.
    contact/     Contact form + email out.
    newsletter/  Double opt-in newsletter signup.
    scheduling/  Booking calendar (see below).
  templates/                     base.html + per-app templates (incl.
                                 scheduling/emails/*).
  static/src/                    Tailwind input + base JS.
  static/dist/                   Built CSS + React island bundle (gitignored).
  staticfiles/                   `collectstatic` output (prod only).
  requirements/                  base.txt / dev.txt / prod.txt
  package.json, tailwind.config.js, postcss.config.js
frontend/
  scheduling-island/             Vite + React + TS source for the booking
                                 widget. Builds into
                                 backend/static/dist/scheduling/.
infra/
  nginx/elbrus.conf              Site config (HTTP->HTTPS, TLS, static,
                                 proxy_pass to gunicorn unix socket).
  systemd/gunicorn.{service,socket}
  deploy/bootstrap.sh            Idempotent one-shot VM provisioner +
                                 redeploy script.
  azure/README.md                Azure CLI commands to provision VM + PG.
md/                              Brand / content reference docs.
```

### Django apps (`INSTALLED_APPS`)

Local apps: `core`, `pages`, `blog`, `contact`, `newsletter`, `scheduling`.
Third-party: `django-robots`. Plus `django.contrib.sitemaps`, `sites`,
`syndication`, the usual contrib set.

`backend/apps/` is added to `sys.path` in `settings/base.py`, so apps are
imported as `core`, `pages`, ... (NOT `apps.core`). Match this convention
in new imports and `INSTALLED_APPS` entries.

### URL surface

Mounted in `backend/elbrus/urls.py`:

- `/`                       - `pages.urls` (home, about, services, contact landing)
- `/blog/`                  - `blog.urls`
- `/contact/`               - `contact.urls`
- `/newsletter/`            - `newsletter.urls`
- `/schedule/`              - `scheduling.urls` (page + JSON API + manage)
- `/admin/`                 - Django admin
- `/sitemap.xml`, `/robots.txt`, `/feed/`, `/healthz`

### Scheduling app (the most complex piece)

Two parallel paths, both live:

1. **Legacy lead-capture** - `BookingInquiry` model + `services_api` +
  `inquiry_api`. Customer leaves contact details; we email the inbox.
2. **Real booking calendar** - `AppointmentType` (bookable meeting kinds),
  `AvailabilityRule` (weekly windows in `SCHEDULING_TIMEZONE`),
   `AvailabilityException` (UTC blackouts), `Booking` (UTC start/end,
   status, opaque `manage_token` UUID for self-serve manage/cancel/reschedule).

Slot generation lives in `apps/scheduling/services/slots.py`. Email
delivery + ICS attachments live in `apps/scheduling/services/email.py`.
The booking JSON API is at `/schedule/api/...` and is consumed by the
React island in `frontend/scheduling-island/`. CSRF is enforced on POST
endpoints (`@csrf_protect`).

Important scheduling settings (env-driven, see `settings/base.py`):

- `SCHEDULING_TIMEZONE` (default `America/New_York`)
- `SCHEDULING_MIN_LEAD_MINUTES` (default 120)
- `SCHEDULING_MAX_LEAD_DAYS` (default 60)
- `SCHEDULING_SLOT_GRANULARITY_MINUTES` (default 15)

Booking conflicts are protected with `select_for_update()` + a
re-check inside `transaction.atomic()`; clients get HTTP 409
`slot_unavailable` if they lose the race.

### React scheduling island

- Source: `frontend/scheduling-island/src/` (App, Stepper, Step* screens,
api.ts, types.ts, dateUtils.ts).
- Build output: `backend/static/dist/scheduling/main.js` (referenced from
`backend/templates/scheduling/index.html`).
- Standalone Vite dev server: `npm run dev` inside the island folder.
- Production build runs as part of `bootstrap.sh`.

### Frontend conventions

- Tailwind input: `backend/static/src/styles.css` ->
`backend/static/dist/styles.css`. Plugins: `@tailwindcss/forms`,
`@tailwindcss/typography`. Built via the standalone Tailwind CLI (no
PostCSS pipeline in Django).
- The base template loads `dist/styles.css`; never hand-edit `dist/`*.
- Don't introduce a global JS framework - the site is intentionally HTML
first. New interactivity should either be a small vanilla snippet or a
separate island, not a SPA shell.
- **Inline scripts must carry a CSP nonce.** Use `{% csp_nonce_attr %}` (or
`nonce="{{ csp_nonce }}"`) inside any `<script>` tag rendered from a
template. The nonce comes from `SecurityHeadersMiddleware`. Loader URLs
constructed inside inline scripts should also propagate the nonce to any
`<script>` elements they create (see the GTM loader in
`partials/_analytics_head.html` for the canonical pattern).
- **Conversion tracking from JS goes through `window.elbrusTrack(name,
payload)`** - never call `gtag`, `fbq`, `lintrk`, `ttq`, etc. directly.
The shim pushes a normalised event onto `dataLayer` and GTM fans it out
to the right vendor. Tracking is no-op when no analytics IDs are
configured, so the call site doesn't need to guard.

---

## Local development

### Prereqs

- Python 3.11+ (the bundled `backend/venv` was created with 3.14).
- Node.js 20+.
- PostgreSQL is **not** required locally - dev defaults to SQLite at
`backend/db.sqlite3`.

### One-time setup

```bash
python -m venv backend/venv
backend\venv\Scripts\activate          # Windows PowerShell
# source backend/venv/bin/activate     # macOS / Linux

pip install -r backend/requirements/dev.txt

copy .env.example .env                 # Windows
# cp .env.example .env                  # macOS / Linux

cd backend && npm install && npm run build:css
cd ../frontend/scheduling-island && npm install && npm run build

cd ../../backend
python manage.py migrate
python manage.py seed                  # services + sample blog post + appointment types
python manage.py createsuperuser
python manage.py runserver             # http://localhost:8000
```

### Day-to-day

- Tailwind watch: `cd backend && npm run watch:css`
- Island dev server: `cd frontend/scheduling-island && npm run dev`
- Tests: `cd backend && pytest` (smoke SEO tests + scheduling tests).
- `python manage.py seed` is idempotent and safe to re-run.

### Settings selection

- Dev (default in `.env.example`): `DJANGO_SETTINGS_MODULE=elbrus.settings.dev`
  - `DEBUG=True`, console email backend, optional `django-debug-toolbar`.
- Prod: `DJANGO_SETTINGS_MODULE=elbrus.settings.prod`
  - `DEBUG=False`, WhiteNoise `CompressedManifestStaticFilesStorage`,
  HSTS, secure cookies, `SECURE_PROXY_SSL_HEADER` set for trust behind Nginx.

---

## Deployment

### Target environment

- **Compute:** single Ubuntu 22.04+ LTS Linux VM on Azure
(`Standard_B2s` is the documented baseline).
- **Process model:** `nginx` (TLS termination, static, reverse proxy) ->
`gunicorn.socket` -> `gunicorn.service` (3 workers, `--timeout 60`,
WSGI app `elbrus.wsgi:application`) running as the `elbrus` system user.
- **DB:** Azure PostgreSQL Flexible Server, private VNet, `sslmode=require`.
- **TLS:** Let's Encrypt via `certbot --nginx`. Nginx config already
reserves `/.well-known/acme-challenge/` at `/var/www/letsencrypt`.
- **Static:** `collectstatic` writes to `/opt/elbrus/app/backend/staticfiles/`,
which Nginx serves directly under `/static/`. WhiteNoise also serves
them through Gunicorn as a fallback.
- **Logs:** `journalctl -u gunicorn -f` and `/var/log/nginx/*.log`.
- **Health check:** `GET /healthz` (plain-text template, no DB hit).

### On-disk layout (VM)

```
/opt/elbrus/
  app/                       git checkout (this repo)
    .env                     production env, mode 0600, owned by elbrus
    backend/staticfiles/     collectstatic output (Nginx serves these)
    backend/static/dist/     built Tailwind CSS + React island bundle
  venv/                      Python virtualenv (gunicorn, django, ...)
/run/elbrus/gunicorn.sock    unix socket between nginx and gunicorn
/etc/systemd/system/         gunicorn.{service,socket}
/etc/nginx/sites-enabled/    elbrus.conf (symlinked from sites-available)
```

### First-time provisioning

1. Provision VM + PostgreSQL Flexible Server via the Azure CLI snippet in
  `infra/azure/README.md`.
2. SSH into the VM, create `/opt/elbrus/app/.env` with prod values
  (template inlined in `infra/azure/README.md`).
3. Download and run the bootstrap script:
  ```bash
   sudo curl -fsSL .../infra/deploy/bootstrap.sh \
       -o /usr/local/sbin/elbrus-bootstrap
   sudo chmod +x /usr/local/sbin/elbrus-bootstrap
   sudo REPO_URL=... BRANCH=main /usr/local/sbin/elbrus-bootstrap
  ```
4. Point DNS at the VM, then `sudo certbot --nginx -d <domain> -d www.<domain>`.

`infra/deploy/bootstrap.sh` is fully idempotent. It installs system
packages, ensures the `elbrus` user, clones/updates the repo, builds the
venv, installs Python + Node deps, builds Tailwind + the React island,
runs `migrate` and `collectstatic`, installs the systemd units +
Nginx site, and reloads services.

### Redeploying

The canonical deploy path is `.github/workflows/deploy.yml`: every push
to `main` runs `pytest` + a Tailwind build, then (only on `push`, not
PRs) invokes `sudo /usr/local/sbin/elbrus-bootstrap` on the
`elbrus-app` VM via `az vm run-command` and verifies the site with a
`curl https://elbruscloud.com/healthz` smoke check. Auth uses OIDC
federated identity — no long-lived secrets in GitHub. Concurrency
group `deploy-prod` queues overlapping deploys instead of cancelling
them. See `infra/azure/README.md` section 7 for the one-time setup
(run `infra/azure/github-actions-setup.sh`, then add five repo
variables).

The fallback path — when CI is down, you need to skip a step, or
you're doing an emergency rollback — is re-running the bootstrap
script directly on the VM:

```bash
sudo /usr/local/sbin/elbrus-bootstrap
```

This does `git pull --ff-only`, reinstalls only changed deps, rebuilds
assets, runs `migrate --noinput` + `collectstatic --noinput`, then
`systemctl restart gunicorn.service`. Typical run is 60-120s.

A manual step-by-step path (when you need to skip / roll back individual
steps) is documented in `infra/azure/README.md` section 5.

### Required production env vars

Lives in `/opt/elbrus/app/.env`, loaded by both Django (via
`environ.Env.read_env`) and the systemd unit (`EnvironmentFile=`).

Must-haves:

- `DJANGO_SETTINGS_MODULE=elbrus.settings.prod`
- `DJANGO_SECRET_KEY` (50+ random chars)
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
- `DJANGO_SECURE_SSL_REDIRECT=True`, `DJANGO_SECURE_HSTS_SECONDS=31536000`
- `DATABASE_URL=postgres://USER:PASS@HOST:5432/elbrus?sslmode=require`
- `SITE_NAME`, `SITE_URL`, `SITE_DOMAIN`, `SITE_DEFAULT_OG_IMAGE`,
`INFO_EMAIL`, `CONTACT_RECIPIENT_EMAIL`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`,
`EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`
- Optional: `SCHEDULING_TIMEZONE`, `SCHEDULING_MIN_LEAD_MINUTES`,
`SCHEDULING_MAX_LEAD_DAYS`, `SCHEDULING_SLOT_GRANULARITY_MINUTES`,
`SENTRY_DSN`.

### Operational notes

- Treat `/opt/elbrus/app/.env` as a secret (mode 0600, owned by `elbrus`).
- Postgres backups: enable Azure-managed automated backups on the
Flexible Server; bump retention beyond the 7-day default for prod.
- HTTPS-only is enforced both at Nginx (301 from :80) and Django
(`SECURE_SSL_REDIRECT`, `SECURE_PROXY_SSL_HEADER`).
- The Gunicorn unit uses `Type=notify` and a `RuntimeDirectory=elbrus`,
so the unix socket dir is auto-created with the right permissions on
start.

---

## Conventions for agents working in this repo

- **Shell:** the local dev machine runs **Windows 11 + PowerShell**. Always
use PowerShell syntax for local commands (`Set-Location`, `Copy-Item`,
`\` path separators, `Activate.ps1`, etc.). Bash/sh is only appropriate
in situations like an SSH session on the Linux VM.
- Don't break the "apps imported by short name" convention - new code
should use `from core.seo import ...`, not `from apps.core.seo import ...`.
- Keep all secrets in `.env` / Azure Key Vault. Never commit
`.env`, `db.sqlite3`, `node_modules`, or anything under
`backend/static/dist/` or `backend/staticfiles/`.
- New pages must keep SEO parity: extend `core.seo.SeoMixin`, supply
`seo_title` / `seo_description`, and add to `core.sitemaps` /
`pages.sitemaps` / `blog.sitemaps` as appropriate. The smoke tests in
`apps/core/tests/test_smoke_seo.py` will fail if a route loses tags.
- Booking-flow changes need a migration **and** updates to the React
island contracts in `frontend/scheduling-island/src/api.ts` /
`types.ts`. The island is built into `backend/static/dist/scheduling/`
by `npm run build`, which `bootstrap.sh` runs on every redeploy.
- When adding env vars, update **all of**: `.env.example`,
`settings/base.py` (with a default), and the prod env template in
`infra/azure/README.md`.
- **New conversion events** must (a) fire via `window.elbrusTrack` (JS) or
the view's `dataLayer_events` context var (server-rendered thanks pages),
(b) be documented in this file, and (c) NOT include PII in the payload.
The event name + a coarse `conversion_type` is enough; GTM enriches from
its own dataLayer state.
- **Lead-capture forms must persist `attribution`.** Any new model that
captures a lead/conversion (contact, booking, newsletter, demo request,
etc.) needs an `attribution = models.JSONField(default=dict, blank=True)`
column wired with `get_attribution_snapshot(request)` in the view that
creates the row. Without this, paid-channel offline conversion uploads
cannot work.
- **Site verification & analytics IDs are opt-in.** All tag templates are
gated on the corresponding env var being non-empty. Adding a new tag
vendor requires adding the env var, the conditional in
`partials/_analytics_head.html`, the new vendor host in the CSP allow-list
inside `core.middleware._SCRIPT_SRC_VENDORS` / `_CONNECT_SRC_VENDORS` /
`_IMG_SRC_VENDORS`, and a test asserting the tag does and does not render
based on the env var.
- Prefer editing `infra/deploy/bootstrap.sh` over inventing new deploy
steps - it is the single source of truth for "what runs on the VM". The
CI workflow in `.github/workflows/deploy.yml` deliberately calls
`elbrus-bootstrap` rather than reimplementing the deploy logic, so any
change to "how we deploy" should land in the bootstrap script first.

