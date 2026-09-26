#!/usr/bin/env bash
# Generuje demo-PKI dla mTLS: Root CA -> Intermediate CA -> (serwer, klienci),
# plus certyfikaty "zepsute" do demonstracji bledow zaufania i CRL.
# Uzycie: ./generate-mtls-pki.sh [katalog-wyjsciowy]   (domyslnie /tmp/prasowka-mtls-pki)
# Klucze sa WYLACZNIE demonstracyjne - nigdy nie commitujemy ich do repo.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-/tmp/prasowka-mtls-pki}"

rm -rf "$OUT"
mkdir -p "$OUT"
CNF="$OUT/ca.cnf"
sed "s#@PKI@#$OUT#g" "$HERE/ca.cnf" > "$CNF"

newkey() { openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$1" 2>/dev/null; }

initca() { # $1 = katalog CA
  mkdir -p "$1/newcerts"
  : > "$1/index.txt"
  echo 1000 > "$1/serial"
  echo 1000 > "$1/crlnumber"
}

# sign <ca_name> <ext_section> <csr> <out.pem> [dodatkowe opcje openssl ca]
sign() {
  local ca="$1" ext="$2" csr="$3" out="$4"
  shift 4
  openssl ca -batch -config "$CNF" -name "$ca" -extensions "$ext" -notext \
    -in "$csr" -out "$out" "$@" 2>/dev/null
}

# leaf <ca_name> <ext_section> <nazwa> <subject> [opcje ca]
leaf() {
  local ca="$1" ext="$2" name="$3" subj="$4"
  shift 4
  newkey "$OUT/$name.key"
  openssl req -new -config "$CNF" -key "$OUT/$name.key" -subj "$subj" -out "$OUT/$name.csr"
  sign "$ca" "$ext" "$OUT/$name.csr" "$OUT/$name.pem" "$@"
}

echo "== Root CA =="
initca "$OUT/root"
newkey "$OUT/root/ca.key"
openssl req -x509 -new -config "$CNF" -key "$OUT/root/ca.key" -sha256 -days 3650 -extensions ext_root \
  -subj "/O=Prasowka Demo/CN=Prasowka mTLS Root CA" -out "$OUT/root/ca.pem"
cp "$OUT/root/ca.pem" "$OUT/root.pem"

echo "== Intermediate CA (podpisany przez root) =="
initca "$OUT/inter"
newkey "$OUT/inter/ca.key"
openssl req -new -config "$CNF" -key "$OUT/inter/ca.key" -subj "/O=Prasowka Demo/CN=Prasowka mTLS Issuing CA" -out "$OUT/inter/ca.csr"
sign ca_root ext_intermediate "$OUT/inter/ca.csr" "$OUT/inter/ca.pem" -days 1825
cp "$OUT/inter/ca.pem" "$OUT/intermediate.pem"

echo "== Serwer (poprawny: SAN + serverAuth) =="
leaf ca_inter ext_server server "/O=Prasowka Demo/CN=localhost"

echo "== Serwer bez SAN (tylko CN) =="
leaf ca_inter ext_server_nosan server-nosan "/O=Prasowka Demo/CN=localhost"

echo "== Klient poprawny (clientAuth) =="
leaf ca_inter ext_client client "/O=Prasowka Demo/CN=alice-service"

echo "== Klient z blednym EKU (serverAuth) =="
leaf ca_inter ext_client_wrongeku client-wrongeku "/O=Prasowka Demo/CN=mallory-wrong-eku"

echo "== Klient wygasly (wazny tylko w styczniu 2025) =="
leaf ca_inter ext_client client-expired "/O=Prasowka Demo/CN=bob-expired" \
  -startdate 20250101000000Z -enddate 20250201000000Z

echo "== Klient do odwolania (CRL) =="
leaf ca_inter ext_client client-revoked "/O=Prasowka Demo/CN=carol-revoked"
openssl ca -batch -config "$CNF" -name ca_inter -revoke "$OUT/client-revoked.pem" -crl_reason keyCompromise 2>/dev/null
openssl ca -batch -config "$CNF" -name ca_inter -gencrl -out "$OUT/inter.crl" 2>/dev/null

echo "== Obca CA (niepowiazana) + klient przez nia podpisany =="
initca "$OUT/rogue"
newkey "$OUT/rogue/ca.key"
openssl req -x509 -new -config "$CNF" -key "$OUT/rogue/ca.key" -sha256 -days 3650 -extensions ext_root \
  -subj "/O=Obca Firma/CN=Obca Root CA" -out "$OUT/rogue/ca.pem"
leaf ca_rogue ext_client client-rogue "/O=Obca Firma/CN=eve-rogue-ca"

echo "Gotowe: $OUT"
ls "$OUT"
