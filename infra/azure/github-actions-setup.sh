#!/usr/bin/env bash
# One-time provisioning for the GitHub Actions -> Azure OIDC trust used by
# .github/workflows/deploy.yml.
#
# What it does:
#   1. Creates (or reuses) an AAD app registration + service principal.
#   2. Grants it `Virtual Machine Contributor` scoped to the single
#      elbrus-app VM (least privilege - enough to invoke runCommand,
#      nothing else).
#   3. Adds a federated credential binding GitHub repo `potap75/elbrusconsult`
#      on ref `refs/heads/main` to that identity, so the workflow can mint
#      a token via OIDC and call Azure without any long-lived secret.
#   4. Prints the 5 values to paste into GitHub repo variables.
#
# Idempotent: re-running is safe; it skips anything that already exists.
#
# Requirements (on your Mac):
#   - az CLI logged in to the subscription that hosts the elbrus-app VM
#     (`az login`, then `az account set --subscription "<name-or-id>"`).
#   - jq installed (`brew install jq`).
#
# Usage:
#   bash infra/azure/github-actions-setup.sh
#
# After it finishes, paste the printed values into:
#   GitHub -> Settings -> Secrets and variables -> Actions -> Variables
# (Variables, NOT secrets - these are non-sensitive identifiers.)

set -euo pipefail

APP_NAME="github-actions-elbruscloud"
REPO="potap75/elbrusconsult"
BRANCH="main"
RG="RG-ELBRUSCLOUD"
VM="elbrus-app"

command -v az >/dev/null 2>&1 || { echo "error: az CLI not found. brew install azure-cli" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "error: jq not found. brew install jq" >&2; exit 1; }

SUB_ID="$(az account show --query id -o tsv)"
TENANT_ID="$(az account show --query tenantId -o tsv)"
SUB_NAME="$(az account show --query name -o tsv)"
VM_SCOPE="/subscriptions/${SUB_ID}/resourceGroups/${RG}/providers/Microsoft.Compute/virtualMachines/${VM}"

echo "==> Subscription: ${SUB_NAME} (${SUB_ID})"
echo "==> Tenant:       ${TENANT_ID}"
echo "==> Target VM:    ${RG}/${VM}"
echo

# Sanity check: the VM must exist (otherwise the role assignment scope is bogus).
if ! az vm show -g "$RG" -n "$VM" --query id -o tsv >/dev/null 2>&1; then
    echo "error: VM ${RG}/${VM} not found in subscription ${SUB_NAME}." >&2
    echo "       Make sure you've selected the right subscription with 'az account set'." >&2
    exit 1
fi

# 1. AAD app registration ----------------------------------------------------
APP_ID="$(az ad app list --display-name "$APP_NAME" --query '[0].appId' -o tsv 2>/dev/null || true)"
if [ -z "$APP_ID" ]; then
    echo "==> Creating AAD app registration '${APP_NAME}'..."
    APP_ID="$(az ad app create --display-name "$APP_NAME" --query appId -o tsv)"
else
    echo "==> Reusing existing AAD app registration (appId=${APP_ID})"
fi

# 2. Service principal -------------------------------------------------------
SP_ID="$(az ad sp list --filter "appId eq '$APP_ID'" --query '[0].id' -o tsv 2>/dev/null || true)"
if [ -z "$SP_ID" ]; then
    echo "==> Creating service principal for app ${APP_ID}..."
    SP_ID="$(az ad sp create --id "$APP_ID" --query id -o tsv)"
else
    echo "==> Reusing existing service principal (id=${SP_ID})"
fi

# 3. Role assignment (least-privilege: just the one VM) ----------------------
EXISTING_ROLE="$(az role assignment list \
    --assignee "$APP_ID" \
    --scope "$VM_SCOPE" \
    --query "[?roleDefinitionName=='Virtual Machine Contributor'].id" \
    -o tsv 2>/dev/null || true)"
if [ -z "$EXISTING_ROLE" ]; then
    echo "==> Assigning 'Virtual Machine Contributor' on ${VM}..."
    # Retry briefly: SP creation can take a few seconds to propagate.
    for i in 1 2 3 4 5; do
        if az role assignment create \
            --assignee "$APP_ID" \
            --role "Virtual Machine Contributor" \
            --scope "$VM_SCOPE" >/dev/null 2>&1; then
            break
        fi
        if [ "$i" = "5" ]; then
            echo "error: role assignment failed after 5 retries" >&2
            exit 1
        fi
        echo "    (SP not yet propagated, retrying in 5s...)"
        sleep 5
    done
else
    echo "==> Role assignment already in place"
fi

# 4. Federated credential (GitHub OIDC trust) --------------------------------
CRED_NAME="github-${REPO//\//-}-${BRANCH}"
EXISTING_CRED="$(az ad app federated-credential list \
    --id "$APP_ID" \
    --query "[?name=='${CRED_NAME}'].name" \
    -o tsv 2>/dev/null || true)"
if [ -z "$EXISTING_CRED" ]; then
    echo "==> Creating federated credential '${CRED_NAME}'..."
    az ad app federated-credential create --id "$APP_ID" --parameters @- >/dev/null <<EOF
{
  "name": "${CRED_NAME}",
  "issuer": "https://token.actions.githubusercontent.com",
  "subject": "repo:${REPO}:ref:refs/heads/${BRANCH}",
  "description": "GitHub Actions auto-deploy from main",
  "audiences": ["api://AzureADTokenExchange"]
}
EOF
else
    echo "==> Federated credential '${CRED_NAME}' already exists"
fi

cat <<EOF

============================================================
  Paste these into GitHub:
    Settings -> Secrets and variables -> Actions -> Variables
    (Variables tab, NOT secrets - these are non-sensitive IDs.)
============================================================
  AZURE_CLIENT_ID        ${APP_ID}
  AZURE_TENANT_ID        ${TENANT_ID}
  AZURE_SUBSCRIPTION_ID  ${SUB_ID}
  AZURE_RG               ${RG}
  AZURE_VM               ${VM}
============================================================

Next: push a trivial commit to main (e.g. a doc tweak). The
'deploy' workflow should run end-to-end and finish with a
green '/healthz' smoke check.
EOF
