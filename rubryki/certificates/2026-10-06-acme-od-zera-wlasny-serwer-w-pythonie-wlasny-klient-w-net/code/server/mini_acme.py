#!/usr/bin/env python3
"""
mini_acme.py - minimalny serwer ACME (RFC 8555) do nauki. NIE do produkcji.

- tylko ES256 (P-256), tylko identyfikatory typu dns, tylko challenge http-01
- stan w pamieci, wlasne demo-CA generowane przy starcie (klucz tylko w pamieci,
  na dysk trafia wylacznie ca.pem - certyfikat publiczny)
- transport: zwykly HTTP na 127.0.0.1 (prawdziwe ACME wymaga HTTPS; tu celowo nie)
- walidacja http-01: serwer lacy sie na 127.0.0.1:<http01-port> z naglowkiem Host: <domena>
  (odpowiednik 'pebble -dnsserver'; prawdziwe CA laczy sie na port 80 domeny)

Uzycie: python3 mini_acme.py --port 14000 --http01-port 5002 --out ../work
"""
import argparse, base64, datetime, hashlib, json, os, secrets, sys, threading, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

LOCK = threading.Lock()
NONCES, ACCOUNTS, ORDERS, AUTHZS, CHALLS, CERTS = set(), {}, {}, {}, {}, {}
CFG = {}


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def thumbprint(jwk: dict) -> str:
    # RFC 7638: tylko wymagane pola, klucze alfabetycznie, bez bialych znakow
    canon = json.dumps({k: jwk[k] for k in ("crv", "kty", "x", "y")}, separators=(",", ":"), sort_keys=True)
    return b64u(hashlib.sha256(canon.encode()).digest())


class AcmeError(Exception):
    def __init__(self, status, typ, detail):
        self.status, self.typ, self.detail = status, typ, detail


def jwk_to_key(jwk):
    if jwk.get("kty") != "EC" or jwk.get("crv") != "P-256":
        raise AcmeError(400, "badPublicKey", "tylko EC P-256")
    x, y = int.from_bytes(unb64u(jwk["x"]), "big"), int.from_bytes(unb64u(jwk["y"]), "big")
    return ec.EllipticCurvePublicNumbers(x, y, ec.SECP256R1()).public_key()


def make_ca():
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Prasowka DEMO"),
                      x509.NameAttribute(NameOID.COMMON_NAME, "Prasowka mini-ACME DEMO CA")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=30))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
            .sign(key, hashes.SHA256()))
    return key, cert


def issue(csr: x509.CertificateSigningRequest, names):
    now = datetime.datetime.now(datetime.timezone.utc)
    ca_key, ca_cert = CFG["ca"]
    b = (x509.CertificateBuilder()
         .subject_name(x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, names[0])]))
         .issuer_name(ca_cert.subject).public_key(csr.public_key())
         .serial_number(x509.random_serial_number())
         .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=7))
         .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
         .add_extension(x509.KeyUsage(True, False, False, False, False, False, False, False, False), critical=True)
         .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
         .add_extension(x509.SubjectAlternativeName([x509.DNSName(n) for n in names]), critical=False)
         .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()), critical=False))
    leaf = b.sign(ca_key, hashes.SHA256())
    return leaf.public_bytes(serialization.Encoding.PEM) + ca_cert.public_bytes(serialization.Encoding.PEM)


def validate_http01(chall_id):
    c = CHALLS[chall_id]
    az = AUTHZS[c["authz"]]
    expected = c["token"] + "." + thumbprint(ACCOUNTS[az["account"]]["jwk"])
    url = f"http://127.0.0.1:{CFG['http01_port']}/.well-known/acme-challenge/{c['token']}"
    req = urllib.request.Request(url, headers={"Host": az["domain"]})
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            body = r.read().decode().strip()
        ok, why = body == expected, ("zla keyAuthorization: oczekiwano ..." + expected[-10:] + ", dostano ..." + body[-10:])
    except Exception as e:  # noqa
        ok, why = False, f"fetch nie powiodl sie: {e}"
    with LOCK:
        if ok:
            c["status"], az["status"] = "valid", "valid"
            c["validated"] = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            for o in ORDERS.values():
                if az_id_of(az) in o["authzs"] and all(AUTHZS[a]["status"] == "valid" for a in o["authzs"]):
                    o["status"] = "ready"
        else:
            err = {"type": "urn:ietf:params:acme:error:unauthorized", "detail": why}
            c["status"], c["error"], az["status"] = "invalid", err, "invalid"
            for o in ORDERS.values():
                if az_id_of(az) in o["authzs"]:
                    o["status"] = "invalid"
    log(f"http-01 {az['domain']}: {'OK' if ok else 'FAIL - ' + why}")


def az_id_of(az):
    return az["id"]


def log(msg):
    print("[acme] " + msg, flush=True)


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *a):
        log(f"{self.command} {self.path} -> {a[1] if len(a) > 1 else ''}")

    @property
    def base(self):
        return f"http://127.0.0.1:{CFG['port']}"

    def send(self, status, body=b"", ctype="application/json", extra=None):
        nonce = b64u(secrets.token_bytes(16))
        with LOCK:
            NONCES.add(nonce)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Replay-Nonce", nonce)
        self.send_header("Cache-Control", "no-store")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, status, obj, extra=None):
        self.send(status, json.dumps(obj).encode(), extra=extra)

    def do_HEAD(self):
        if self.path == "/new-nonce":
            self.send(200)
        else:
            self.send(404)

    def do_GET(self):
        if self.path == "/directory":
            b = self.base
            self.send_json(200, {"newNonce": b + "/new-nonce", "newAccount": b + "/new-acct", "newOrder": b + "/new-order",
                                 "meta": {"termsOfService": b + "/tos-demo"}})
        elif self.path == "/new-nonce":
            self.send(204)
        else:
            # RFC 8555 6.3: zasoby przez POST-as-GET; zwykly GET -> 405
            self.send_json(405, {"type": "urn:ietf:params:acme:error:malformed", "detail": "uzyj POST-as-GET"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            payload, acct_id = self.verify_jws(raw)
            self.route(payload, acct_id)
        except AcmeError as e:
            self.send(e.status, json.dumps({"type": "urn:ietf:params:acme:error:" + e.typ, "detail": e.detail}).encode(),
                      ctype="application/problem+json")
            log(f"ODRZUCONO {self.path}: {e.typ}: {e.detail}")

    # ---- JWS (RFC 8555 6.2, RFC 7515) ----
    def verify_jws(self, raw):
        try:
            j = json.loads(raw)
            prot_b, pay_b, sig_b = j["protected"], j["payload"], j["signature"]
            prot = json.loads(unb64u(prot_b))
            sig = unb64u(sig_b)
        except Exception:
            raise AcmeError(400, "malformed", "nieprawidlowy JWS (JSON flattened)")
        if prot.get("alg") != "ES256":
            raise AcmeError(400, "badSignatureAlgorithm", f"alg={prot.get('alg')!r}, wspierane: ES256")
        if ("jwk" in prot) == ("kid" in prot):
            raise AcmeError(400, "malformed", "dokladnie jedno z: jwk, kid")
        if prot.get("url") != self.base + self.path:
            raise AcmeError(401, "unauthorized", f"naglowek url {prot.get('url')!r} != {self.base + self.path!r}")
        nonce = prot.get("nonce")
        with LOCK:
            if nonce not in NONCES:
                raise AcmeError(400, "badNonce", "nonce nieznany lub juz uzyty")
            NONCES.discard(nonce)  # jednorazowy
        acct_id = None
        if "jwk" in prot:
            key = jwk_to_key(prot["jwk"])
        else:
            acct_id = prot["kid"].rsplit("/", 1)[-1]
            if prot["kid"] != f"{self.base}/acct/{acct_id}" or acct_id not in ACCOUNTS:
                raise AcmeError(401, "accountDoesNotExist", "nieznany kid")
            key = jwk_to_key(ACCOUNTS[acct_id]["jwk"])
        if len(sig) != 64:  # ES256 w JWS to r||s (2x32 B), NIE DER
            raise AcmeError(400, "malformed", f"podpis ES256 ma {len(sig)} B; wymagane 64 (r||s, nie DER)")
        try:
            key.verify(encode_dss_signature(int.from_bytes(sig[:32], "big"), int.from_bytes(sig[32:], "big")),
                       (prot_b + "." + pay_b).encode(), ec.ECDSA(hashes.SHA256()))
        except InvalidSignature:
            raise AcmeError(403, "unauthorized", "podpis JWS nie zgadza sie z kluczem")
        payload = None if pay_b == "" else json.loads(unb64u(pay_b))  # "" = POST-as-GET
        if "jwk" in prot:
            payload = {"__jwk": prot["jwk"], **(payload or {})}
        return payload, acct_id

    # ---- routing ----
    def route(self, p, acct_id):
        b = self.base
        path = self.path
        if path == "/new-acct":
            jwk = p.pop("__jwk")
            tp = thumbprint(jwk)
            with LOCK:
                existing = next((i for i, a in ACCOUNTS.items() if thumbprint(a["jwk"]) == tp), None)
                if existing is None:
                    if p.get("onlyReturnExisting"):
                        raise AcmeError(400, "accountDoesNotExist", "brak konta dla tego klucza")
                    if not p.get("termsOfServiceAgreed"):
                        raise AcmeError(403, "userActionRequired", "wymagana akceptacja ToS")
                    existing = secrets.token_hex(4)
                    ACCOUNTS[existing] = {"jwk": jwk, "contact": p.get("contact", [])}
                    code = 201
                else:
                    code = 200
            self.send_json(code, {"status": "valid", "contact": ACCOUNTS[existing]["contact"], "orders": b + "/orders/" + existing},
                           {"Location": f"{b}/acct/{existing}"})
            return
        if acct_id is None:
            raise AcmeError(401, "unauthorized", "ten endpoint wymaga kid (konto), nie jwk")
        if path == "/new-order":
            ids = p.get("identifiers", [])
            if not ids or any(i.get("type") != "dns" for i in ids):
                raise AcmeError(400, "rejectedIdentifier", "tylko identyfikatory dns")
            oid, authz_ids = secrets.token_hex(4), []
            with LOCK:
                for i in ids:
                    aid, cid = secrets.token_hex(4), secrets.token_hex(4)
                    AUTHZS[aid] = {"id": aid, "domain": i["value"], "status": "pending", "account": acct_id, "chall": cid}
                    CHALLS[cid] = {"id": cid, "authz": aid, "token": b64u(secrets.token_bytes(32)), "status": "pending"}
                    authz_ids.append(aid)
                ORDERS[oid] = {"id": oid, "ids": ids, "authzs": authz_ids, "status": "pending", "account": acct_id}
            self.send_json(201, self.order_json(oid), {"Location": f"{b}/order/{oid}"})
        elif path.startswith("/authz/"):
            self.send_json(200, self.authz_json(path.rsplit("/", 1)[-1]))
        elif path.startswith("/chall/"):
            cid = path.rsplit("/", 1)[-1]
            c = CHALLS.get(cid)
            if not c:
                raise AcmeError(404, "malformed", "nieznany challenge")
            with LOCK:
                if c["status"] == "pending":
                    c["status"] = "processing"
                    threading.Thread(target=validate_http01, args=(cid,), daemon=True).start()
            self.send_json(200, self.chall_json(cid), {"Link": f'<{b}/authz/{c["authz"]}>;rel="up"'})
        elif path.startswith("/order/") and path.endswith("/finalize"):
            oid = path.split("/")[2]
            o = ORDERS.get(oid)
            if not o:
                raise AcmeError(404, "malformed", "nieznane zamowienie")
            if o["status"] != "ready":
                raise AcmeError(403, "orderNotReady", f"status zamowienia: {o['status']}")
            try:
                csr = x509.load_der_x509_csr(unb64u(p["csr"]))
                assert csr.is_signature_valid
                san = csr.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
            except Exception as e:
                raise AcmeError(400, "badCSR", f"CSR nieczytelny lub bez SAN/podpisu: {e}")
            want = sorted(i["value"] for i in o["ids"])
            if sorted(san) != want:
                raise AcmeError(400, "badCSR", f"SAN w CSR {sorted(san)} != identyfikatory zamowienia {want}")
            pem = issue(csr, [i["value"] for i in o["ids"]])
            with LOCK:
                CERTS[oid] = pem
                o["status"] = "valid"
            self.send_json(200, self.order_json(oid), {"Location": f"{b}/order/{oid}"})
        elif path.startswith("/order/"):
            self.send_json(200, self.order_json(path.rsplit("/", 1)[-1]))
        elif path.startswith("/cert/"):
            pem = CERTS.get(path.rsplit("/", 1)[-1])
            if not pem:
                raise AcmeError(404, "malformed", "brak certyfikatu")
            self.send(200, pem, ctype="application/pem-certificate-chain")
        else:
            raise AcmeError(404, "malformed", "nieznany endpoint")

    def order_json(self, oid):
        o, b = ORDERS[oid], self.base
        d = {"status": o["status"], "identifiers": o["ids"], "authorizations": [f"{b}/authz/{a}" for a in o["authzs"]],
             "finalize": f"{b}/order/{oid}/finalize"}
        if o["status"] == "valid":
            d["certificate"] = f"{b}/cert/{oid}"
        return d

    def authz_json(self, aid):
        a = AUTHZS[aid]
        return {"status": a["status"], "identifier": {"type": "dns", "value": a["domain"]}, "challenges": [self.chall_json(a["chall"])]}

    def chall_json(self, cid):
        c = CHALLS[cid]
        d = {"type": "http-01", "url": f"{self.base}/chall/{cid}", "token": c["token"], "status": c["status"]}
        if "error" in c:
            d["error"] = c["error"]
        if "validated" in c:
            d["validated"] = c["validated"]
        return d


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=14000)
    ap.add_argument("--http01-port", type=int, default=5002)
    ap.add_argument("--out", default="../work")
    a = ap.parse_args()
    CFG.update(port=a.port, http01_port=a.http01_port, ca=make_ca())
    os.makedirs(a.out, exist_ok=True)
    with open(os.path.join(a.out, "ca.pem"), "wb") as f:
        f.write(CFG["ca"][1].public_bytes(serialization.Encoding.PEM))
    log(f"mini-ACME na http://127.0.0.1:{a.port}/directory, http-01 -> 127.0.0.1:{a.http01_port}, ca.pem w {a.out}")
    ThreadingHTTPServer(("127.0.0.1", a.port), H).serve_forever()


if __name__ == "__main__":
    main()
