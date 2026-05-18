# Azure deployment notes

This document walks through provisioning the Azure resources needed to host
Elbrus Cloud, then handing the VM off to
[`../deploy/bootstrap.sh`](../deploy/bootstrap.sh).

Two pieces of cloud infrastructure are required:

1. **Linux VM (Ubuntu 22.04+ LTS)** running Nginx + Gunicorn + the Django app.
2. **Azure Database for PostgreSQL - Flexible Server** for the application
   database.

Optionally:

- **Azure Storage Account** (Blob) for user-uploaded media, swapped in via
  `django-storages` once we have real uploads. Not required for the initial
  launch.

---

## 1. Provision resources (Azure CLI)

```bash
# Variables you can tweak
RG=elbrus-prod
LOC=eastus
VNET=elbrus-vnet
SUBNET_APP=app
SUBNET_DB=db
VM_NAME=elbrus-app
VM_SIZE=Standard_B2s
PG_NAME=elbrus-pg
PG_ADMIN=elbrusdba
PG_DB=elbrus

az group create -n $RG -l $LOC

# Network
az network vnet create -g $RG -n $VNET --address-prefix 10.20.0.0/16 \
  --subnet-name $SUBNET_APP --subnet-prefix 10.20.1.0/24
az network vnet subnet create -g $RG --vnet-name $VNET \
  -n $SUBNET_DB --address-prefixes 10.20.2.0/24 \
  --delegations Microsoft.DBforPostgreSQL/flexibleServers

# VM
az vm create -g $RG -n $VM_NAME \
  --image Ubuntu2204 \
  --size $VM_SIZE \
  --admin-username elbrusops \
  --ssh-key-values ~/.ssh/id_ed25519.pub \
  --vnet-name $VNET --subnet $SUBNET_APP \
  --public-ip-sku Standard

az vm open-port -g $RG -n $VM_NAME --port 80  --priority 1010
az vm open-port -g $RG -n $VM_NAME --port 443 --priority 1011
az vm open-port -g $RG -n $VM_NAME --port 22  --priority 1012

# PostgreSQL Flexible Server (private access via VNet)
az postgres flexible-server create \
  -g $RG -n $PG_NAME -l $LOC \
  --admin-user $PG_ADMIN \
  --admin-password "$(openssl rand -base64 24)" \
  --vnet $VNET --subnet $SUBNET_DB \
  --version 16 \
  --tier Burstable --sku-name Standard_B1ms \
  --storage-size 32 \
  --high-availability Disabled \
  --yes

az postgres flexible-server db create \
  -g $RG --server-name $PG_NAME --database-name $PG_DB
```

After this runs, you will have:

- A VM with a public IP and SSH access.
- A private Postgres Flexible Server reachable from the `app` subnet.

The Postgres admin password is printed by the `flexible-server create`
command. Store it in a secure vault (Azure Key Vault, 1Password, etc.).

---

## 2. Prepare the VM

SSH in:

```bash
ssh elbrusops@<public-ip>
```

Create the `.env` file the application will read:

```bash
sudo mkdir -p /opt/elbrus/app
sudo chown elbrusops:elbrusops /opt/elbrus/app

cat <<'EOF' | sudo tee /opt/elbrus/app/.env > /dev/null
DJANGO_SETTINGS_MODULE=elbrus.settings.prod
DJANGO_SECRET_KEY=<generate-a-50-char-random-string>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=elbruscloud.example,www.elbruscloud.example
DJANGO_CSRF_TRUSTED_ORIGINS=https://elbruscloud.example,https://www.elbruscloud.example
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000

SITE_NAME=Elbrus Cloud
SITE_TAGLINE=Cloud Engineering & Cybersecurity Excellence
SITE_DOMAIN=elbruscloud.example
SITE_URL=https://elbruscloud.example
SITE_DEFAULT_OG_IMAGE=/static/img/og-default.png
INFO_EMAIL=info@elbruscloud.example
CONTACT_RECIPIENT_EMAIL=info@elbruscloud.example

DATABASE_URL=postgres://elbrusdba:<password>@elbrus-pg.postgres.database.azure.com:5432/elbrus?sslmode=require

EMAIL_HOST=<smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-pass>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Elbrus Cloud <no-reply@elbruscloud.example>
EOF
sudo chmod 600 /opt/elbrus/app/.env
```

---

## 3. Bootstrap the application

From the VM:

```bash
sudo curl -fsSL \
  https://raw.githubusercontent.com/your-org/elbrusconsult/main/infra/deploy/bootstrap.sh \
  -o /usr/local/sbin/elbrus-bootstrap
sudo chmod +x /usr/local/sbin/elbrus-bootstrap
sudo REPO_URL=https://github.com/your-org/elbrusconsult.git BRANCH=main \
  /usr/local/sbin/elbrus-bootstrap
```

The script installs Python/Node/Nginx, clones the repo into
`/opt/elbrus/app`, creates the venv at `/opt/elbrus/venv`, builds Tailwind
and the React scheduling island, runs `migrate` and `collectstatic`, then
installs and starts the Gunicorn systemd units and the Nginx site.

---

## 4. Get TLS

Once DNS points at the VM:

```bash
sudo certbot --nginx -d elbruscloud.example -d www.elbruscloud.example
```

Certbot will edit the Nginx config in place and set up automatic renewal.

---

## 5. Pulling changes on the VM

### Quick path — re-run the bootstrap script

The bootstrap script is fully idempotent. Re-running it is the safest and
recommended way to deploy any set of changes:

```bash
sudo /usr/local/sbin/elbrus-bootstrap
```

What it does in order:

1. `git fetch` + `git pull --ff-only` on the `main` branch.
2. `pip install -r backend/requirements/prod.txt` (only installs new/changed packages).
3. `npm install` + `npm run build:css` (Tailwind) and `npm run build` (React island).
4. `python manage.py migrate --noinput`
5. `python manage.py collectstatic --noinput`
6. Restarts `gunicorn.service`.

The whole run usually takes 60–120 seconds. Watch it live:

```bash
sudo /usr/local/sbin/elbrus-bootstrap 2>&1 | tee /tmp/deploy.log
```

---

### Manual step-by-step path

Use this if you want finer control or need to roll back a single step.

**1. SSH into the VM**

```bash
ssh elbrusops@<public-ip>
```

**2. Pull the latest code**

```bash
sudo -u elbrus git -C /opt/elbrus/app fetch --all --prune
sudo -u elbrus git -C /opt/elbrus/app pull --ff-only
```

**3. Install any new Python dependencies**

```bash
sudo -u elbrus /opt/elbrus/venv/bin/pip install -r /opt/elbrus/app/backend/requirements/prod.txt
```

**4. Rebuild frontend assets** (skip if only Python/template changes)

```bash
# Tailwind CSS
sudo -u elbrus bash -lc "cd /opt/elbrus/app/backend && npm install --no-audit --no-fund && npm run build:css"

# React scheduling island
sudo -u elbrus bash -lc "cd /opt/elbrus/app/frontend/scheduling-island && npm install --no-audit --no-fund && npm run build"
```

**5. Run database migrations**

```bash
sudo -u elbrus bash -lc "
  cd /opt/elbrus/app/backend
  DJANGO_SETTINGS_MODULE=elbrus.settings.prod \
    /opt/elbrus/venv/bin/python manage.py migrate --noinput
"
```

**6. Collect static files**

```bash
sudo -u elbrus bash -lc "
  cd /opt/elbrus/app/backend
  DJANGO_SETTINGS_MODULE=elbrus.settings.prod \
    /opt/elbrus/venv/bin/python manage.py collectstatic --noinput
"
```

**7. Restart Gunicorn**

```bash
sudo systemctl restart gunicorn.service
```

Verify the service came back up:

```bash
sudo systemctl status gunicorn.service
```

**8. (Optional) Reload Nginx**

Only needed if the Nginx config changed:

```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

### Verifying the deployment

```bash
# Tail Gunicorn logs for errors
journalctl -u gunicorn -f

# Quick HTTP health check
curl -sf https://elbruscloud.example/healthz && echo "OK"
```

---

## 6. Known gotchas

### Rate limiter 500 errors (calendar greyed out)

`django-ratelimit` raises `ImproperlyConfigured` when `REMOTE_ADDR` is empty,
which always happens when Gunicorn runs behind Nginx via a Unix socket. The fix
— `RATELIMIT_IP_META_KEY = "HTTP_X_REAL_IP"` — is already set in
`settings/prod.py` and tells ratelimit to use the `X-Real-IP` header that Nginx
injects from `$remote_addr`. No `.env` change is needed, but if you ever see
`500` responses on `/schedule/api/slots/` or other rate-limited endpoints, this
is the first thing to check in the Gunicorn logs.

### Gunicorn fails to start (status=226/NAMESPACE)

Systemd namespace-based sandboxing directives (`PrivateTmp`, `ProtectSystem`,
etc.) are not supported on Azure B-series VMs when the service runs as a
non-root user. The `infra/systemd/gunicorn.service` shipped in this repo omits
those directives intentionally.

---

## 7. Operational notes

- **Logs:** `journalctl -u gunicorn -f` and `/var/log/nginx/*.log`.
- **Health check:** `https://elbruscloud.example/healthz`.
- **Backups:** Configure Azure-managed automated backups on the Flexible
  Server. Default retention is 7 days; bump for production.
- **Secrets:** Treat `/opt/elbrus/app/.env` as a secret. Mode 600, owned by
  the `elbrus` user. Consider Azure Key Vault + a small fetch script for a
  hardened setup.
