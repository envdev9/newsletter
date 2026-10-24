#!/usr/bin/env python3
"""
Wydanie #14 (2026-10-07): pomocnik do zywego serwera TeamCity w Dockerze.
Rozwija tc_live.py z wydania #13 (kreator pierwszego startu przez HTTP + RSA po stylu
TeamCity, uniwersalne REST, "Show DSL" jako ZIP). Zmiany: haslo z pliku, REST z jawnym
JSON, polling statusu.

Uzycie:
    python3 tc_live.py wizard                      # caly kreator: instalacja, HSQLDB, licencja, admin
    python3 tc_live.py rest METHOD PATH [PLIK_BODY|-] [ctype] [accept]   # dowolne wywolanie REST
    python3 tc_live.py show-dsl PROJECT_ID OUT.zip # "Download settings in Kotlin format"
    python3 tc_live.py poll PATH NEEDLE [SEKUNDY]  # czeka az odpowiedz REST (JSON) zawiera NEEDLE

Haslo admina (EFEMERYCZNY kontener demo): zmienna srodowiskowa TC_ADMIN_PASSWORD albo
plik wskazany przez TC_ADMIN_PASSWORD_FILE (domyslnie /tmp/prasowka-devops-IdMMom/tc-p14-work/password.txt).
Skrypt nie ma zadnego hasla w kodzie. Adres serwera: TC_BASE.
"""
import base64
import http.cookiejar
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = os.environ.get("TC_BASE", "http://localhost:8111")
ADMIN_USER = "admin"
ADMIN_PASSWORD = os.environ.get("TC_ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    _pf = os.environ.get("TC_ADMIN_PASSWORD_FILE", "/tmp/prasowka-devops-IdMMom/tc-p14-work/password.txt")
    if os.path.exists(_pf):
        with open(_pf, "r", encoding="utf-8") as _f:
            ADMIN_PASSWORD = _f.read().strip()
if not ADMIN_PASSWORD:
    raise SystemExit("Ustaw TC_ADMIN_PASSWORD albo TC_ADMIN_PASSWORD_FILE (haslo efemerycznego serwera demo)")

_cj = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
_AUTH = "Basic " + base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()


def http_get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    try:
        r = _opener.open(req, timeout=30)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def http_post_form(path, fields):
    req = urllib.request.Request(
        BASE + path,
        data=urllib.parse.urlencode(fields).encode(),
        headers={"User-Agent": "Mozilla/5.0"},
        method="POST",
    )
    try:
        r = _opener.open(req, timeout=60)
        return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def rest(method, path, body=None, ctype="application/xml", accept="application/xml"):
    headers = {"Authorization": _AUTH, "Accept": accept}
    data = None
    if body is not None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        headers["Content-Type"] = ctype
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def rsa_encrypt(message: bytes, modulus: int, exponent: int) -> str:
    """TeamCity-owy wariant PKCS#1 v1.5: za wiadomoscia dodatkowy bajt = jej dlugosc
    (patrz wydanie #8). Wynik dopelniony zerami do 2*k znakow hex."""
    msg = message + bytes([len(message)])
    k = (modulus.bit_length() + 7) // 8
    ps_len = k - 3 - len(msg)
    if ps_len < 8:
        raise ValueError("message too long")
    ps = bytearray()
    while len(ps) < ps_len:
        b = os.urandom(1)
        if b != b"\x00":
            ps += b
    block = b"\x00\x02" + bytes(ps) + b"\x00" + msg
    c = pow(int.from_bytes(block, "big"), exponent, modulus)
    return format(c, "x").zfill(2 * k)


def stage():
    s, b = http_get("/mnt")
    m = re.search(r"Stage: (\w+)", b.decode("utf-8", "ignore"))
    return (m.group(1) if m else "?"), b.decode("utf-8", "ignore")


def wait_stage(want, timeout=300):
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        st, txt = stage()
        print("stage:", st)
        if st == want or (want == "FIRST" and st != "APPLICATION_STARTING"):
            return st, txt
        time.sleep(5)
    raise SystemExit("timeout waiting for " + want)


def cmd_wizard():
    """Cala sciezka kreatora W JEDNYM PROCESIE - sesja (cookie) musi przetrwac
    miedzy krokami, inaczej serwer odpowiada 'The session is not authenticated'."""
    import time
    st, txt = wait_stage("FIRST")
    print("goNewInstallation ->", http_post_form("/mnt/do/goNewInstallation", {"restore": "false"}))
    wait_stage("DB_SETTINGS_SCREEN")
    print("goNewDatabase ->", http_post_form("/mnt/do/goNewDatabase", {"dbType": "HSQLDB2"}))
    for _ in range(120):
        st, txt = stage()
        print("stage:", st)
        if "agreement" in txt.lower() and "accept" in txt.lower() and "tc-csrf-token" in txt:
            break
        if st == "?" or "createAdmin" in txt or "publicKey" in txt:
            break
        time.sleep(5)
    m = re.search(r'name="tc-csrf-token" value="([^"]+)"', txt)
    token = m.group(1) if m else ""
    if "publicKey" not in txt:
        print("showAgreement ->", http_post_form(
            "/showAgreement.html",
            {"accept": "true", "_accept": "", "sendUsageStatistics": "false",
             "_sendUsageStatistics": "", "tc-csrf-token": token})[0])
    for _ in range(120):
        s, b = http_get("/mnt")
        txt = b.decode("utf-8", "ignore")
        m = re.search(r'id="publicKey" name="publicKey" value="([0-9a-fA-F]+)"', txt)
        if m:
            break
        print("czekam na formularz admina...", re.findall(r"Stage: \w+", txt))
        time.sleep(5)
    else:
        raise SystemExit("formularz admina nie pojawil sie")
    pub = m.group(1)
    n = int(pub, 16)
    pw = ADMIN_PASSWORD.encode()
    s, b = http_post_form(
        "/createAdminSubmit.html",
        {"username1": ADMIN_USER, "publicKey": pub,
         "encryptedPassword1": rsa_encrypt(pw, n, 0x10001),
         "encryptedRetypedPassword": rsa_encrypt(pw, n, 0x10001),
         "submitCreateUser": "Create Account"},
    )
    print("createAdminSubmit ->", s, b[:200])


def cmd_rest(args):
    method, path = args[0], args[1]
    body = None
    ctype = "application/xml"
    if len(args) > 2 and args[2] != "-":
        with open(args[2], "r", encoding="utf-8") as f:
            body = f.read()
    accept = "application/xml"
    if len(args) > 3:
        ctype = args[3]
        if ctype == "text/plain":
            accept = "text/plain"   # REST zwraca 406, jesli Accept nie pasuje do typu zasobu
        elif ctype == "application/json":
            accept = "application/json"
    if len(args) > 4:
        accept = args[4]
    s, b = rest(method, path, body, ctype, accept)
    print(s)
    print(b.decode("utf-8", "replace"))


def cmd_show_dsl(project_id, out):
    url = (BASE + "/admin/versionedSettingsActions.html?projectId=" + project_id
           + "&action=generate&format=kotlin&version=latest")
    req = urllib.request.Request(url, headers={"Authorization": _AUTH})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    with open(out, "wb") as f:
        f.write(data)
    print(f"zapisano {len(data)} bajtow do {out}")


def cmd_poll(path, needle, timeout=300):
    """Odpytuje REST co 5 s, az odpowiedz zawiera needle; wypisuje czas oczekiwania."""
    import time
    t0 = time.time()
    while time.time() - t0 < timeout:
        s, b = rest("GET", path, None, accept="application/json")
        txt = b.decode("utf-8", "replace")
        if needle in txt:
            print(f"po {time.time() - t0:.0f} s: {s} {txt[:600]}")
            return
        time.sleep(5)
    s, b = rest("GET", path, None, accept="application/json")
    print(f"TIMEOUT po {timeout} s; ostatnia odpowiedz: {s} {b.decode('utf-8', 'replace')[:600]}")


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    if a[0] == "wizard":
        cmd_wizard()
    elif a[0] == "rest":
        cmd_rest(a[1:])
    elif a[0] == "show-dsl":
        cmd_show_dsl(a[1], a[2])
    elif a[0] == "poll":
        cmd_poll(a[1], a[2], int(a[3]) if len(a) > 3 else 300)
    else:
        raise SystemExit(__doc__)
