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
DJANGO_ALLOWED_HOSTS=elbruscloud.com,www.elbruscloud.com
DJANGO_CSRF_TRUSTED_ORIGINS=https://elbruscloud.com,https://www.elbruscloud.com
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000

SITE_NAME=Elbrus Cloud
SITE_TAGLINE=Cloud Engineering & Cybersecurity Excellence
SITE_DOMAIN=elbruscloud.com
SITE_URL=https://elbruscloud.com
SITE_DEFAULT_OG_IMAGE=/static/img/og-default.png
INFO_EMAIL=info@elbruscloud.com
CONTACT_RECIPIENT_EMAIL=info@elbruscloud.com
SITE_ADVISORY_PHONE=+1 (704) 686-8481

DATABASE_URL=postgres://elbrusdba:<password>@elbrus-pg.postgres.database.azure.com:5432/elbrus?sslmode=require

EMAIL_HOST=<smtp-host>
EMAIL_PORT=587
EMAIL_HOST_USER=<smtp-user>
EMAIL_HOST_PASSWORD=<smtp-pass>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=Elbrus Cloud <no-reply@elbruscloud.com>

# Analytics & paid-channel tag manager (all optional; tags only render when set)
# GTM is the single source of truth for marketing pixels — configure GA4,
# Google Ads, LinkedIn Insight, Meta Pixel, Microsoft UET, and TikTok Pixel
# INSIDE the GTM container, not as separate <script> tags in this repo.
GTM_CONTAINER_ID=GTM-5LFJD8D4
GA4_MEASUREMENT_ID=G-JD3TKNY687
GOOGLE_ADS_CONVERSION_ID=
LINKEDIN_PARTNER_ID=
META_PIXEL_ID=
BING_UET_TAG_ID=
TIKTOK_PIXEL_ID=

# Search engine site verification (paste the meta-tag CONTENT value only)
GOOGLE_SITE_VERIFICATION=
BING_SITE_VERIFICATION=

# Google Consent Mode v2: deny by default (privacy-by-default; consent
# banner upgrades to granted on user accept). CONSENT_DEFAULT_DENY_REGIONS
# is optional; useful only if you ever set CONSENT_DEFAULT_GRANTED=True.
CONSENT_DEFAULT_GRANTED=False
CONSENT_DEFAULT_DENY_REGIONS=

# First-touch attribution cookie lifetime (days). 90 = Google Ads default.
ATTRIBUTION_COOKIE_DAYS=90
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
sudo certbot --nginx -d elbruscloud.com -d www.elbruscloud.com
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
curl -sf https://elbruscloud.com/healthz && echo "OK"
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

## 7. CI/CD via GitHub Actions

`.github/workflows/deploy.yml` is the canonical deploy path. Every push and
PR to `main` runs `pytest` and a Tailwind build; pushes (not PRs)
additionally invoke `sudo /usr/local/sbin/elbrus-bootstrap` on the
`elbrus-app` VM via `az vm run-command`, then verify the site is live with
a `curl https://elbruscloud.com/healthz` smoke check (six retries, 30s
total). The manual deploy path documented in section 5 remains the
fallback for emergency rollbacks or when CI is unavailable.

Authentication to Azure is via OIDC federated identity, so there are no
long-lived secrets stored in GitHub.

### One-time setup

1. Log in to the Azure CLI on your laptop and select the right subscription:

   ```bash
   az login
   az account set --subscription "<name-or-id of the sub that hosts elbrus-app>"
   ```

2. Run the provisioning script from the repo root:

   ```bash
   bash infra/azure/github-actions-setup.sh
   ```

   This creates an AAD app registration, a matching service principal,
   grants it `Virtual Machine Contributor` scoped to **only** the
   `elbrus-app` VM (no broader access), and adds a federated credential
   binding the GitHub repo + `refs/heads/main` to that identity. The
   script is idempotent — re-running it is safe.

3. Paste the five values it prints into **Settings → Secrets and variables
   → Actions → Variables** on the GitHub repo (Variables tab, *not*
   Secrets — these are non-sensitive identifiers):

   | Variable name           | Value                                    |
   |-------------------------|------------------------------------------|
   | `AZURE_CLIENT_ID`       | App registration `appId`                 |
   | `AZURE_TENANT_ID`       | Tenant ID                                |
   | `AZURE_SUBSCRIPTION_ID` | Subscription ID                          |
   | `AZURE_RG`              | `RG-ELBRUSCLOUD`                         |
   | `AZURE_VM`              | `elbrus-app`                             |

4. Push a trivial commit to `main`. The `deploy` workflow should run
   end-to-end and finish with a green `/healthz` check.

### Day-to-day

- Open a PR to `main` → tests run, deploy is skipped.
- Merge to `main` → tests run, then deploy fires.
- Concurrency group `deploy-prod` queues overlapping deploys instead of
  cancelling them, so two rapid merges land in order.
- The federated credential is bound to `refs/heads/main` only, so PRs
  from forks cannot mint Azure tokens.

### When `/healthz` fails after a deploy

1. Open the workflow run on GitHub and read the bootstrap output captured
   under the **"Run bootstrap on the VM"** step (last 150 lines).
2. SSH in and tail Gunicorn:

   ```bash
   ssh elbrusops@<public-ip>
   journalctl -u gunicorn -f
   ```

3. If the deploy left the box in a broken state, roll forward with a
   revert commit (which will trigger a fresh deploy) or use the manual
   step-by-step path in section 5 to fix in place.

---

## 8. Operational notes

- **Logs:** `journalctl -u gunicorn -f` and `/var/log/nginx/*.log`.
- **Health check:** `https://elbruscloud.com/healthz`.
- **Backups:** Configure Azure-managed automated backups on the Flexible
  Server. Default retention is 7 days; bump for production.
- **Secrets:** Treat `/opt/elbrus/app/.env` as a secret. Mode 600, owned by
  the `elbrus` user. Consider Azure Key Vault + a small fetch script for a
  hardened setup.
