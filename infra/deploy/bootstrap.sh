#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Elbrus Cloud - one-shot VM bootstrap.
#
# Assumes a fresh Ubuntu 22.04+ LTS VM on Azure. Run as a sudo-capable user.
# Steps:
#   1. Install system packages (Python, Node, Nginx, certbot).
#   2. Create the `elbrus` system user.
#   3. Clone the repo (or expect it already cloned at /opt/elbrus/app).
#   4. Create the venv, install Python deps.
#   5. Build the React island + Tailwind CSS.
#   6. Run migrate + collectstatic.
#   7. Install systemd units + Nginx config.
#   8. Reload services.
#
# It is idempotent enough to re-run after a `git pull` to redeploy.
# ---------------------------------------------------------------------------
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/your-org/elbrusconsult.git}"
APP_ROOT="/opt/elbrus"
APP_DIR="${APP_ROOT}/app"
VENV_DIR="${APP_ROOT}/venv"
BRANCH="${BRANCH:-main}"

log() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }

# -------------------------------------------------------------------------
log "Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y \
    python3 python3-venv python3-dev build-essential \
    nginx certbot python3-certbot-nginx \
    git curl ca-certificates \
    libpq-dev pkg-config

# Node.js 20 LTS via NodeSource.
if ! command -v node >/dev/null 2>&1; then
    log "Installing Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

# -------------------------------------------------------------------------
log "Ensuring 'elbrus' system user..."
if ! id elbrus >/dev/null 2>&1; then
    sudo useradd --system --create-home --home-dir "${APP_ROOT}" \
                 --shell /usr/sbin/nologin elbrus
fi
sudo mkdir -p "${APP_ROOT}"
sudo chown -R elbrus:elbrus "${APP_ROOT}"

# -------------------------------------------------------------------------
log "Fetching application code..."
if [ ! -d "${APP_DIR}/.git" ]; then
    sudo -u elbrus git clone --branch "${BRANCH}" "${REPO_URL}" "${APP_DIR}"
else
    sudo -u elbrus git -C "${APP_DIR}" fetch --all --prune
    sudo -u elbrus git -C "${APP_DIR}" checkout "${BRANCH}"
    sudo -u elbrus git -C "${APP_DIR}" pull --ff-only
fi

# -------------------------------------------------------------------------
log "Setting up Python virtualenv..."
if [ ! -d "${VENV_DIR}" ]; then
    sudo -u elbrus python3 -m venv "${VENV_DIR}"
fi
sudo -u elbrus "${VENV_DIR}/bin/pip" install --upgrade pip wheel
sudo -u elbrus "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/backend/requirements/prod.txt"

# -------------------------------------------------------------------------
log "Building frontend assets..."
# Tailwind CSS
sudo -u elbrus bash -lc "cd '${APP_DIR}/backend' && npm install --no-audit --no-fund && npm run build:css"
# React scheduling island
sudo -u elbrus bash -lc "cd '${APP_DIR}/frontend/scheduling-island' && npm install --no-audit --no-fund && npm run build"

# -------------------------------------------------------------------------
log "Running Django management commands..."
if [ ! -f "${APP_DIR}/.env" ]; then
    log "WARNING: ${APP_DIR}/.env is missing. Copy .env.example and fill in real values."
fi
sudo -u elbrus bash -lc "cd '${APP_DIR}/backend' && \
    DJANGO_SETTINGS_MODULE=elbrus.settings.prod '${VENV_DIR}/bin/python' manage.py migrate --noinput"
sudo -u elbrus bash -lc "cd '${APP_DIR}/backend' && \
    DJANGO_SETTINGS_MODULE=elbrus.settings.prod '${VENV_DIR}/bin/python' manage.py collectstatic --noinput"

# -------------------------------------------------------------------------
log "Setting up ads engine (remote MCP) virtualenv..."
ADENGINE_VENV="${APP_ROOT}/adengine-venv"
if [ ! -d "${ADENGINE_VENV}" ]; then
    sudo -u elbrus python3 -m venv "${ADENGINE_VENV}"
fi
sudo -u elbrus "${ADENGINE_VENV}/bin/pip" install --upgrade pip wheel
sudo -u elbrus "${ADENGINE_VENV}/bin/pip" install -r "${APP_DIR}/adengine/requirements.txt"

if [ ! -f "${APP_ROOT}/adengine.env" ]; then
    log "WARNING: ${APP_ROOT}/adengine.env is missing. The ads engine will"
    log "         start but reject requests (503). See infra/mcp/README.md."
fi

# -------------------------------------------------------------------------
log "Installing systemd units..."
sudo install -m 0644 "${APP_DIR}/infra/systemd/gunicorn.service" /etc/systemd/system/gunicorn.service
sudo install -m 0644 "${APP_DIR}/infra/systemd/gunicorn.socket"  /etc/systemd/system/gunicorn.socket
sudo install -m 0644 "${APP_DIR}/infra/systemd/adengine.service" /etc/systemd/system/adengine.service
sudo systemctl daemon-reload
sudo systemctl enable --now gunicorn.socket
sudo systemctl restart gunicorn.service
sudo systemctl enable adengine.service
sudo systemctl restart adengine.service

# -------------------------------------------------------------------------
log "Installing nginx site..."
sudo install -m 0644 "${APP_DIR}/infra/nginx/elbrus.conf" /etc/nginx/sites-available/elbrus.conf
sudo ln -sf /etc/nginx/sites-available/elbrus.conf /etc/nginx/sites-enabled/elbrus.conf
sudo rm -f /etc/nginx/sites-enabled/default

# The ads engine HTTPS block references its TLS cert, so it is only enabled
# once certbot has issued one (the elbrus.conf :80 block already serves the
# ACME challenge for mcp.elbruscloud.com, so issuance works either way).
sudo install -m 0644 "${APP_DIR}/infra/nginx/adengine.conf" /etc/nginx/sites-available/adengine.conf
if [ -f /etc/letsencrypt/live/mcp.elbruscloud.com/fullchain.pem ]; then
    sudo ln -sf /etc/nginx/sites-available/adengine.conf /etc/nginx/sites-enabled/adengine.conf
else
    log "NOTE: mcp.elbruscloud.com cert not found; adengine nginx site staged"
    log "      but not enabled. Run: sudo certbot --nginx -d mcp.elbruscloud.com"
    sudo rm -f /etc/nginx/sites-enabled/adengine.conf
fi

sudo nginx -t
sudo systemctl reload nginx

log "Bootstrap complete."
log "Next steps: point DNS at this VM, then run:"
log "  sudo certbot --nginx -d elbruscloud.com -d www.elbruscloud.com"
log "  sudo certbot --nginx -d mcp.elbruscloud.com   # ads engine endpoint"
