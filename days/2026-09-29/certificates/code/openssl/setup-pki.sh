#!/usr/bin/env bash
# End-to-end demo of the RFC 6962 "Certificate Transparency" precertificate
# mechanism, using ONLY openssl for X.509 work and our own CtLab .NET tool for
# everything RFC 6962-specific (leaf hashing, SCT, Merkle tree, STH).
#
# WARNING: everything here is a throwaway DEMO PKI + a throwaway "CT log"
# keypair. None of it is a real, trusted CA and none of it talks to a real
# CT log. Do not reuse any of these keys for anything real.
#
# Usage: bash setup-pki.sh [workdir]   (default: ./work next to this script)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${1:-$SCRIPT_DIR/../work}"
CTLAB="$SCRIPT_DIR/../dotnet/CtLab/CtLab.csproj"
mkdir -p "$WORK/precertdb/newcerts" "$WORK/finaldb/newcerts" "$WORK/finaldb2/newcerts"

echo "== workdir: $WORK =="

# ---------------------------------------------------------------------------
# 1. Demo CT CA (self-signed, EC P-256) and demo CT log operator keypair.
# ---------------------------------------------------------------------------
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 \
  -keyout "$WORK/ca.key" -out "$WORK/ca.pem" -days 3650 -nodes -sha256 \
  -subj "/O=Prasowka Demo/CN=Prasowka CT Demo CA"

openssl ecparam -genkey -name prime256v1 -noout -out "$WORK/ctlog.key"
openssl ec -in "$WORK/ctlog.key" -pubout -out "$WORK/ctlog.pub"

# ---------------------------------------------------------------------------
# 2. Leaf keypair + CSR for the certificate we will run through the CT dance.
# ---------------------------------------------------------------------------
openssl ecparam -genkey -name prime256v1 -noout -out "$WORK/leaf.key"
openssl req -new -key "$WORK/leaf.key" -out "$WORK/leaf.csr" -sha256 \
  -subj "/O=Prasowka Demo/CN=ct-demo.local"

# ---------------------------------------------------------------------------
# 3. Two independent tiny openssl-ca "databases" for the SAME CA key/cert.
#    We need this because we must issue the precert and the final cert with
#    the IDENTICAL serial number and IDENTICAL notBefore/notAfter (that is a
#    hard CT/CA-Browser-Forum requirement: the final cert must be
#    byte-identical to the precert except for the poison<->SCT-list swap).
#    `openssl ca` lets us fix serial/dates exactly; two separate index/serial
#    files avoid a "serial already used" clash between the two issuances.
# ---------------------------------------------------------------------------
write_ca_cnf() {
  local dbdir="$1" out="$2"
  cat > "$out" <<EOF
[ca]
default_ca = CA_default

[CA_default]
dir               = $dbdir
database          = $dbdir/index.txt
new_certs_dir     = $dbdir/newcerts
serial            = $dbdir/serial
certificate       = $WORK/ca.pem
private_key       = $WORK/ca.key
default_md        = sha256
policy            = policy_anything
email_in_dn       = no
unique_subject    = no
copy_extensions   = none
default_days      = 365

[policy_anything]
countryName            = optional
stateOrProvinceName    = optional
organizationName       = optional
organizationalUnitName = optional
commonName             = supplied
emailAddress           = optional
EOF
}

for db in precertdb finaldb finaldb2; do
  : > "$WORK/$db/index.txt"
  echo 1001 > "$WORK/$db/serial"
  write_ca_cnf "$WORK/$db" "$WORK/ca-$db.cnf"
done

START="20260929000000Z"
END="20270929000000Z"

# ---------------------------------------------------------------------------
# 4. Precertificate: normal leaf extensions + the critical "CT poison"
#    extension (1.3.6.1.4.1.11129.2.4.3 = NULL). A precert must never be
#    served to a real client - the poison is exactly what stops that from
#    happening by accident (any RFC-5280-correct client MUST reject an
#    unrecognized critical extension).
# ---------------------------------------------------------------------------
cat > "$WORK/precert.ext" <<'EOF'
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:ct-demo.local
1.3.6.1.4.1.11129.2.4.3=critical,ASN1:NULL
EOF

openssl ca -config "$WORK/ca-precertdb.cnf" -in "$WORK/leaf.csr" \
  -out "$WORK/precert.pem" -extfile "$WORK/precert.ext" \
  -startdate "$START" -enddate "$END" -batch -notext

echo "-- precert issued; poison extension: --"
openssl x509 -in "$WORK/precert.pem" -noout -ext 1.3.6.1.4.1.11129.2.4.3

# ---------------------------------------------------------------------------
# 5. Build the .NET tool once.
# ---------------------------------------------------------------------------
dotnet build "$CTLAB" -v q

# ---------------------------------------------------------------------------
# 6. "Submit" the precert to our own demo CT log: compute the RFC 6962
#    leaf hash, sign a real SignedCertificateTimestamp with the log key,
#    and get back a ready-to-use openssl -extfile fragment.
# ---------------------------------------------------------------------------
TS_MS="$(($(date -u +%s) * 1000))"
dotnet run --project "$CTLAB" -c Release -- issue-sct \
  "$WORK/ca.pem" "$WORK/precert.pem" "$WORK/ctlog.key" "$WORK/ctlog.pub" "$TS_MS" \
  "$WORK/sctlist-extvalue.bin" "$WORK/leafhash.bin" "$WORK/sct.extfile.txt"

# ---------------------------------------------------------------------------
# 7. Final certificate: identical extensions, poison swapped for the real
#    SCT list extension (1.3.6.1.4.1.11129.2.4.2, non-critical).
# ---------------------------------------------------------------------------
cat > "$WORK/final.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:ct-demo.local
$(cat "$WORK/sct.extfile.txt")
EOF

openssl ca -config "$WORK/ca-finaldb.cnf" -in "$WORK/leaf.csr" \
  -out "$WORK/final.pem" -extfile "$WORK/final.ext" \
  -startdate "$START" -enddate "$END" -batch -notext

echo "-- final cert issued; openssl's OWN generic ASN.1 parser sees the extension: --"
openssl asn1parse -in "$WORK/final.pem" | grep -A1 "CT Precertificate SCTs"

# ---------------------------------------------------------------------------
# 8. Independent verification, purely from the final certificate + the log's
#    public key (a real CT monitor never sees precert.pem, only this).
# ---------------------------------------------------------------------------
dotnet run --project "$CTLAB" -c Release -- strip "$WORK/precert.pem" \
  1.3.6.1.4.1.11129.2.4.3 "$WORK/precert-tbs-nopoison.bin"

echo "== verify-final (should all say OK) =="
dotnet run --project "$CTLAB" -c Release -- verify-final \
  "$WORK/final.pem" "$WORK/ctlog.pub" "$WORK/ca.pem" "$WORK/precert-tbs-nopoison.bin"

# ---------------------------------------------------------------------------
# 9. Negative demo: reuse the SAME SCT on a certificate with a different SAN.
#    This must FAIL verification - that is the entire point of CT: an SCT is
#    a signature over the exact bytes that were logged, not a rubber stamp.
# ---------------------------------------------------------------------------
cat > "$WORK/tampered.ext" <<EOF
basicConstraints=critical,CA:FALSE
keyUsage=critical,digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=DNS:evil-ct-demo.local
$(cat "$WORK/sct.extfile.txt")
EOF

openssl ca -config "$WORK/ca-finaldb2.cnf" -in "$WORK/leaf.csr" \
  -out "$WORK/final-tampered.pem" -extfile "$WORK/tampered.ext" \
  -startdate "$START" -enddate "$END" -batch -notext

echo "== verify-final on the tampered cert (must FAIL) =="
dotnet run --project "$CTLAB" -c Release -- verify-final \
  "$WORK/final-tampered.pem" "$WORK/ctlog.pub" "$WORK/ca.pem" "$WORK/precert-tbs-nopoison.bin" \
  || echo "(non-zero exit above is EXPECTED - the tampered cert must not verify)"

# ---------------------------------------------------------------------------
# 10. Merkle tree: put our leaf among a few synthetic filler leaves, get an
#     inclusion (audit) proof, verify it recomputes the published root; then
#     build+sign+verify a Signed Tree Head for that root.
# ---------------------------------------------------------------------------
echo "== Merkle inclusion proof =="
dotnet run --project "$CTLAB" -c Release -- merkle-demo "$WORK/leafhash.bin" 5 3

STH_TS_MS="$(($(date -u +%s) * 1000 + 30000))"
echo "== Signed Tree Head =="
dotnet run --project "$CTLAB" -c Release -- sth "$WORK/tree-root.bin" 6 "$STH_TS_MS" \
  "$WORK/ctlog.key" "$WORK/ctlog.pub"

echo "== Merkle audit-path self-test (many tree sizes/indices) =="
dotnet run --project "$CTLAB" -c Release -- selftest-merkle

echo "== done =="
