# Elbrus Cloud

Marketing website for **Elbrus Cloud** - a cloud architecture & cybersecurity
consulting firm.

- **Backend:** Django 5 (server-rendered templates, Tailwind, full SEO stack)
- **Frontend island:** React + Vite for the scheduling widget placeholder
- **Database:** PostgreSQL (Azure Database for PostgreSQL - Flexible Server in prod)
- **Hosting:** Linux VM on Azure (Nginx + Gunicorn + systemd)

## Pages

Home, About, Services, Blog, Contact, Newsletter (double opt-in), and a
Scheduling page (currently a placeholder + lead-capture form via React).

---

## Local development

### Prerequisites

- Python 3.11+ (the repo's existing `backend/venv` was built with 3.14)
- Node.js 20+ (for Tailwind and the React island)
- A working PostgreSQL is **not** required locally - dev defaults to SQLite.

### Setup

```bash
# 1. Create / activate a virtualenv (or reuse backend/venv)
python -m venv backend/venv
backend\venv\Scripts\activate          # Windows PowerShell
# source backend/venv/bin/activate      # macOS / Linux

# 2. Install Python deps
pip install -r backend/requirements/dev.txt

# 3. Copy env file
copy .env.example .env                  # Windows
# cp .env.example .env                   # macOS / Linux

# 4. Build CSS once so the templates have something to load
cd backend
npm install
npm run build:css

# 5. Build the React scheduling island (optional - the page works without it)
cd ../frontend/scheduling-island
npm install
npm run build

# 6. Migrate + seed + run
cd ../../backend
python manage.py migrate
python manage.py seed                   # creates services + a sample blog post
python manage.py createsuperuser
python manage.py runserver
```

Open http://localhost:8000.

### Tailwind

Tailwind builds from `backend/static/src/styles.css` to
`backend/static/dist/styles.css` via the standalone CLI.

```bash
cd backend
npm install                            # one-time, installs Tailwind + plugins
npm run watch:css                      # watch mode for development
npm run build:css                      # production (minified) build
```

### Scheduling React island

```bash
cd frontend/scheduling-island
npm install
npm run dev                            # standalone Vite dev preview
npm run build                          # outputs to backend/static/dist/scheduling/
```

The island is mounted from the Django-rendered `/schedule/` page.

---

## Project layout

```
backend/                Django project + apps
  elbrus/settings/      base.py, dev.py, prod.py
  apps/                 core, pages, blog, contact, newsletter, scheduling
  templates/            base.html + per-app templates
  static/src/           Tailwind input + base JS
  static/dist/          built CSS + React island bundle (gitignored)
frontend/
  scheduling-island/    Vite + React + TS placeholder for future booking UI
infra/
  nginx/                Nginx site config
  systemd/              gunicorn.service / gunicorn.socket
  deploy/               bootstrap.sh for one-shot VM setup
  azure/                README for Azure provisioning notes
md/                     Brand / content reference docs
```

## SEO

Every page renders fully on the server with:

- `<title>`, `<meta description>`, canonical link, robots meta
- Open Graph + Twitter Card tags
- JSON-LD: `Organization`, `WebSite`, `Article`, `BreadcrumbList`,
  `LocalBusiness`, `Service`
- `sitemap.xml`, `robots.txt`, RSS feed for the blog
- HTTPS-only redirect + HSTS in production

Run the smoke test to verify SEO tags are present on every route:

```bash
cd backend
pytest apps/core/tests
```

## Deployment

See [`infra/azure/README.md`](infra/azure/README.md) for Azure VM and
PostgreSQL Flexible Server setup, plus the on-VM stack (Nginx + Gunicorn +
systemd) wired up by [`infra/deploy/bootstrap.sh`](infra/deploy/bootstrap.sh).
