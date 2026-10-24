#!/usr/bin/env bash
# DEV-ONLY CA + node certificates for mutual TLS (Redis broker <-> API/workers). Use step-ca, cert-manager or Vault PKI in production.
set -euo pipefail
cd "$(dirname "$0")"; mkdir -p ca nodes
[ -f ca/ca.crt ] || openssl req -x509 -newkey rsa:4096 -nodes -keyout ca/ca.key -out ca/ca.crt -days 365 -subj "/CN=deepoptima-ca"
NODES=("$@"); [ ${#NODES[@]} -eq 0 ] && NODES=(api worker-1 redis)
for n in "${NODES[@]}"; do
  openssl req -newkey rsa:2048 -nodes -keyout "nodes/$n.key" -out "nodes/$n.csr" -subj "/CN=$n"
  openssl x509 -req -in "nodes/$n.csr" -CA ca/ca.crt -CAkey ca/ca.key -CAcreateserial -out "nodes/$n.crt" -days 90
  chmod 644 "nodes/$n.key"   # dev convenience so the container user can read it; tighten in production
  echo "$n: $(openssl x509 -in "nodes/$n.crt" -noout -fingerprint -sha256)"
done
