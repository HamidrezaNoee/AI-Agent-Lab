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
chmod 700 .secrets
printf '%s\n' 'Internal identity secrets initialized; existing secrets preserved.'
