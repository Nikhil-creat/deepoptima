#!/usr/bin/env bash
# Dev CA + per-node client certs for mTLS between workers and control plane. Use cert-manager/step-ca/Vault PKI in prod.
set -euo pipefail
mkdir -p ca nodes; cd "$(dirname "$0")"
openssl req -x509 -newkey rsa:4096 -nodes -keyout ca/ca.key -out ca/ca.crt -days 365 -subj "/CN=deepoptima-ca"
for n in "${@:-api worker-1}"; do
  openssl req -newkey rsa:2048 -nodes -keyout nodes/$n.key -out nodes/$n.csr -subj "/CN=$n"
  openssl x509 -req -in nodes/$n.csr -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial -out nodes/$n.crt -days 90
  echo "$n fingerprint: $(openssl x509 -in nodes/$n.crt -noout -fingerprint -sha256)"
done
