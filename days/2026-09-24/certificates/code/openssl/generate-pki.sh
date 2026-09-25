#!/usr/bin/env bash
# Generuje od zera minimalne, DEMONSTRACYJNE PKI:
#   1. własne root CA (self-signed) - "urząd", któremu ręcznie każemy ufać
#   2. certyfikat "leaf" podpisany tym CA (to jest normalny, "prawidłowy" przypadek)
#   3. certyfikat "rogue" - też self-signed, ale NIE podpisany naszym CA
#      (symuluje typowy realny problem: serwer wystawia sam sobie certyfikat,
#      klient nie ma powodu mu ufać -> "self signed certificate" w logach)
#
# UWAGA BEZPIECZEŃSTWA: wszystkie klucze prywatne wygenerowane przez ten skrypt
# są WYŁĄCZNIE demonstracyjne/edukacyjne. Nigdy nie używaj ich do niczego
# produkcyjnego ani nie traktuj jako czegokolwiek poufnego - to jednorazowy,
# odtwarzalny przykład do nauki.
#
# Użycie:
#   ./generate-pki.sh [katalog-wyjściowy]   # domyślnie ./pki
set -euo pipefail

OUT_DIR="${1:-$(dirname "$0")/pki}"
rm -rf "$OUT_DIR"
mkdir -p "$OUT_DIR"
OUT_DIR="$(cd "$OUT_DIR" && pwd)"
cd "$OUT_DIR"

echo "=== 1. Klucz prywatny root CA (RSA 4096) ==="
openssl genrsa -out ca.key 4096

echo
echo "=== 2. Self-signed certyfikat root CA (to jest KORZEŃ zaufania) ==="
openssl req -x509 -new -key ca.key -sha256 -days 3650 \
  -subj "/C=PL/O=Prasowka Demo CA/CN=Prasowka Root CA" \
  -out ca.pem

echo
echo "=== 3. Klucz prywatny certyfikatu leaf (RSA 2048) ==="
openssl genrsa -out leaf.key 2048

echo
echo "=== 4. CSR (Certificate Signing Request) dla leaf ==="
openssl req -new -key leaf.key \
  -subj "/C=PL/O=Prasowka Demo/CN=api.prasowka.local" \
  -out leaf.csr

cat > leaf.ext <<'EOF'
subjectAltName=DNS:api.prasowka.local
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
EOF

echo
echo "=== 5. Podpisanie CSR naszym CA -> certyfikat leaf.pem (CA-signed) ==="
openssl x509 -req -in leaf.csr -CA ca.pem -CAkey ca.key -CAcreateserial \
  -days 825 -sha256 -extfile leaf.ext -out leaf.pem

echo
echo "=== 6. Certyfikat 'rogue' - self-signed, BEZ powiązania z naszym CA ==="
openssl req -x509 -new -newkey rsa:2048 -nodes -keyout rogue.key -days 365 \
  -subj "/C=PL/O=Rogue Self-Signed/CN=rogue.local" -out rogue.pem

echo
echo "=== Zawartość leaf.pem (openssl x509 -text) ==="
openssl x509 -in leaf.pem -text -noout

echo
echo "=== Weryfikacja przez 'openssl verify' ==="
echo "-- leaf.pem względem naszego CA (oczekiwane: OK) --"
openssl verify -CAfile ca.pem leaf.pem || true
echo "-- rogue.pem względem naszego CA (oczekiwane: BŁĄD, bo to inny, niepowiązany certyfikat) --"
openssl verify -CAfile ca.pem rogue.pem || true

echo
echo "Gotowe. Pliki w: $OUT_DIR"
ls -1 "$OUT_DIR"
