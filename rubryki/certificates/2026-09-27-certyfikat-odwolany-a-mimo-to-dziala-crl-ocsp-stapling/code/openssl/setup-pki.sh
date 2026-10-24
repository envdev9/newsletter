#!/usr/bin/env bash
# Demo-PKI dla wydania #4: Root -> Issuing CA -> certyfikaty serwera z CDP/AIA.
# Uzycie: bash setup-pki.sh [katalog]   (domyslnie code/work, ignorowany przez git)
# UWAGA: ten skrypt NIE byl uruchomiony w calosci (srodowisko odrzucilo uruchomienie);
# wszystkie komendy z niego wykonano recznie, pojedynczo - patrz ARTICLE.md.
# Klucze WYLACZNIE demonstracyjne, generowane poza repo.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HERE/../work}"; mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"

rm -rf "$OUT"
mkdir -p "$OUT"
CNF="$OUT/ca.cnf"
sed "s#@PKI@#$OUT#g" "$HERE/ca.cnf" > "$CNF"

newkey() { openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out "$1" 2>/dev/null; }
initca() { mkdir -p "$1/newcerts"; : > "$1/index.txt"; echo 1000 > "$1/serial"; echo 1000 > "$1/crlnumber"; }
sign() { # ca ext csr out [opcje]
  local ca="$1" ext="$2" csr="$3" out="$4"; shift 4
  openssl ca -batch -config "$CNF" -name "$ca" -extensions "$ext" -notext -in "$csr" -out "$out" "$@" 2>/dev/null
}
leaf() { # ca ext nazwa subject [opcje]   (klucz: <nazwa>.key; nowy, chyba ze istnieje)
  local ca="$1" ext="$2" name="$3" subj="$4"; shift 4
  [ -f "$OUT/$name.key" ] || newkey "$OUT/$name.key"
  openssl req -new -config "$CNF" -key "$OUT/$name.key" -subj "$subj" -out "$OUT/$name.csr"
  sign "$ca" "$ext" "$OUT/$name.csr" "$OUT/$name.pem" "$@"
}

initca "$OUT/root"; newkey "$OUT/root/ca.key"
openssl req -x509 -new -config "$CNF" -key "$OUT/root/ca.key" -sha256 -days 3650 -extensions ext_root \
  -subj "/O=Prasowka Demo/CN=Prasowka Rev Root CA" -out "$OUT/root/ca.pem"
cp "$OUT/root/ca.pem" "$OUT/root.pem"

initca "$OUT/inter"; newkey "$OUT/inter/ca.key"
openssl req -new -config "$CNF" -key "$OUT/inter/ca.key" -subj "/O=Prasowka Demo/CN=Prasowka Rev Issuing CA" -out "$OUT/inter/ca.csr"
sign ca_root ext_intermediate "$OUT/inter/ca.csr" "$OUT/inter/ca.pem" -days 1825
cp "$OUT/inter/ca.pem" "$OUT/intermediate.pem"

# certyfikaty serwera
leaf ca_inter ext_server         srv-good     "/O=Prasowka Demo/CN=localhost"
leaf ca_inter ext_server         srv-revoked  "/O=Prasowka Demo/CN=localhost"
leaf ca_inter ext_server_deadcdp srv-deadcdp  "/O=Prasowka Demo/CN=localhost"
# odnowienie z TYM SAMYM kluczem (rotacja "renew"): CSR z klucza srv-good, nowy certyfikat
openssl req -new -config "$CNF" -key "$OUT/srv-good.key" -subj "/O=Prasowka Demo/CN=localhost" -out "$OUT/srv-renewed-samekey.csr"
sign ca_inter ext_server "$OUT/srv-renewed-samekey.csr" "$OUT/srv-renewed-samekey.pem"
# odnowienie z NOWYM kluczem (rotacja "rekey")
leaf ca_inter ext_server         srv-rekeyed "/O=Prasowka Demo/CN=localhost"

# responder OCSP
leaf ca_inter ext_ocsp ocsp "/O=Prasowka Demo/CN=Prasowka OCSP Responder"

# odwolanie srv-revoked + CRL
openssl ca -batch -config "$CNF" -name ca_inter -revoke "$OUT/srv-revoked.pem" -crl_reason keyCompromise 2>/dev/null
openssl ca -batch -config "$CNF" -name ca_inter -gencrl -out "$OUT/inter.crl" 2>/dev/null

# "przeterminowany" CRL (nextUpdate w przeszlosci) - do eksperymentu ze stale CRL
openssl ca -batch -config "$CNF" -name ca_inter -gencrl -crl_lastupdate 20260901000000Z -crl_nextupdate 20260910000000Z \
  -out "$OUT/inter-stale.crl" 2>/dev/null

echo "Gotowe: $OUT"
ls "$OUT"
