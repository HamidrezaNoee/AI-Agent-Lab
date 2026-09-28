#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
umask 077
mkdir -p .secrets
for name in keycloak-db-password avan-bff-client-secret avan-provisioner-client-secret; do
  if [ ! -f ".secrets/$name" ]; then
    openssl rand -base64 64 | tr -d '\n=' | tr '+/' '-_' > ".secrets/$name"
  fi
  chmod 600 ".secrets/$name"
done
if [ ! -f .secrets/avan-sql-sa-password ]; then
  printf 'Avan1!%s' "$(openssl rand -base64 48 | tr -d '\n=' | tr '+/' '-_')" > .secrets/avan-sql-sa-password
fi
chmod 600 .secrets/avan-sql-sa-password
if [ ! -f .secrets/avan-antibot-hmac-key ]; then
  openssl rand -base64 64 | tr -d '\n=' | tr '+/' '-_' > .secrets/avan-antibot-hmac-key
fi
chmod 600 .secrets/avan-antibot-hmac-key
chmod 700 .secrets
printf '%s\n' 'Internal identity and database secrets initialized; existing secrets preserved.'
printf '%s\n' 'Self-hosted AVAN anti-bot secret initialized; no external CAPTCHA key is required.'
