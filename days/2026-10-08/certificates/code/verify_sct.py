#!/usr/bin/env python3
"""Niezalezna weryfikacja SCT (inny jezyk, inna biblioteka) dla certyfikatow wyprodukowanych przez SctGate.

Uzycie: python3 verify_sct.py work/leaf-S2.pem work/root.pem work/log1-pub.pem [work/log2-pub.pem ...]
Czyta WYLACZNIE certyfikaty i klucze publiczne. TBS precertu bierze z biblioteki cryptography
(tbs_precertificate_bytes), a nie z kodu .NET - wiec rekonstrukcja DER tez jest sprawdzana niezaleznie.
"""
import datetime
import hashlib
import struct
import sys

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

SCT_OID = "1.3.6.1.4.1.11129.2.4.2"
leaf_path, root_path, *log_paths = sys.argv[1:]
leaf = x509.load_pem_x509_certificate(open(leaf_path, "rb").read())
root = x509.load_pem_x509_certificate(open(root_path, "rb").read())


def spki(pub):
    return pub.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


logs = {}
for p in log_paths:
    pub = serialization.load_pem_public_key(open(p, "rb").read())
    logs[hashlib.sha256(spki(pub)).digest()] = pub

issuer_hash = hashlib.sha256(spki(root.public_key())).digest()
tbs = leaf.tbs_precertificate_bytes
ext = leaf.extensions.get_extension_for_class(x509.PrecertificateSignedCertificateTimestamps)

# surowy extnValue (DER OCTET STRING z lista TLS) - po to, by wyjac surowe podpisy
raw_ext = [e for e in leaf.extensions if e.oid.dotted_string == SCT_OID][0].value.public_bytes()
i = 2 if raw_ext[1] < 0x80 else 2 + (raw_ext[1] & 0x7F)
lst = raw_ext[i:]
total = struct.unpack(">H", lst[:2])[0]
raw_scts = []
p = 2
while p < 2 + total:
    n = struct.unpack(">H", lst[p:p + 2])[0]
    raw_scts.append(lst[p + 2:p + 2 + n])
    p += 2 + n

print(f"{leaf_path}: SCT-ow w certyfikacie: {len(ext.value)}")
for sct, raw in zip(ext.value, raw_scts):
    ts_ms = round((sct.timestamp - datetime.datetime(1970, 1, 1)).total_seconds() * 1000)
    elen = struct.unpack(">H", raw[41:43])[0]
    q = 43 + elen
    siglen = struct.unpack(">H", raw[q + 2:q + 4])[0]
    sig = raw[q + 4:q + 4 + siglen]
    signed = (b"\x00\x00" + struct.pack(">Q", ts_ms) + b"\x00\x01" + issuer_hash
              + len(tbs).to_bytes(3, "big") + tbs + b"\x00\x00")
    head = f"  log_id={sct.log_id.hex()[:8]}... ts_ms={ts_ms} {sct.version.name} {sct.entry_type.name}"
    pub = logs.get(sct.log_id)
    if pub is None:
        print(head + ": NIEZNANY LOG")
        continue
    try:
        pub.verify(sig, signed, ec.ECDSA(hashes.SHA256()))
        print(head + ": podpis OK")
    except InvalidSignature:
        print(head + ": podpis NIEPOPRAWNY")
