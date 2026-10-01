#!/usr/bin/env python3
"""
Skrypt uzyty w wydaniu #8 (2026-10-01) do automatycznego przejscia calego
kreatora pierwszego startu zywego serwera TeamCity (jetbrains/teamcity-server
w Dockerze) oraz skonfigurowania przez REST API projektu demonstrujacego
build feature "Automatic Merge" - bez dotykania przegladarki.

Wymaga: `docker run -d --name tc-demo -p 8111:8111 jetbrains/teamcity-server:2025.07`
i chwili (ok. 1-2 min) na wewnetrzna inicjalizacje.

Uzycie (kazda komenda w osobnym wywolaniu, w tej kolejnosci):
    python3 teamcity-server-setup.py new-installation
    python3 teamcity-server-setup.py accept-license
    python3 teamcity-server-setup.py create-admin
    python3 teamcity-server-setup.py setup-demo-project
    python3 teamcity-server-setup.py show-dsl

Haslo administratora jest na stale wpisane ponizej (ADMIN_PASSWORD) - to
haslo do EFEMERYCZNEGO kontenera Dockera, ktory istnieje wylacznie na czas
tej sesji weryfikacyjnej i zostaje usuniety na jej koniec (zob. ARTICLE.md /
README.md, sekcja "Sprzatanie"). Nie jest to sekret produkcyjny.

Kluczowe odkrycie udokumentowane w tym skrypcie: TeamCity szyfruje hasla
przesylane w formularzach webowych (tworzenie admina, logowanie) kluczem RSA
generowanym raz na cykl zycia serwera (udostepnianym w ukrytym polu
"publicKey" formularza), uzywajac WLASNEJ, NIESTANDARDOWEJ odmiany paddingu
PKCS#1 v1.5 (zob. funkcja `pkcs1_pad_encrypt_with_length_marker` nizej) -
odtworzonej tutaj przez (a) przeczytanie client-side JS
(/js/crypt/rsa.js, funkcja pkcs1pad2) ORAZ (b) disasemblacje (`javap`)
server-side klasy jetbrains.buildServer.serverSide.crypt.RSACipher z
pobranego `common.jar`, dla niezaleznego potwierdzenia formatu bloku.
"""
import base64
import http.cookiejar
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://localhost:8111"
ADMIN_USER = "admin"
ADMIN_PASSWORD = "PrasowkaDemo2026!"

_cj = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_cj))
_AUTH_HEADER = "Basic " + base64.b64encode(f"{ADMIN_USER}:{ADMIN_PASSWORD}".encode()).decode()


def http_get(path):
    req = urllib.request.Request(BASE + path, headers={"User-Agent": "Mozilla/5.0"})
    try:
        resp = _opener.open(req, timeout=20)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def http_post_form(path, fields: dict):
    body = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(
        BASE + path, data=body, headers={"User-Agent": "Mozilla/5.0"}, method="POST"
    )
    try:
        resp = _opener.open(req, timeout=30)
        return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def rest(method, path, body=None, content_type="application/xml"):
    headers = {"Authorization": _AUTH_HEADER, "Accept": "application/xml"}
    data = None
    if body is not None:
        data = body.encode("utf-8") if isinstance(body, str) else body
        headers["Content-Type"] = content_type
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def pkcs1_pad_encrypt_with_length_marker(message: bytes, modulus: int, exponent: int) -> str:
    """
    Replika TeamCity-owej (NIE standardowej jsbn) funkcji `pkcs1pad2` z
    js/crypt/rsa.js. Różni się od "podręcznikowego" PKCS#1 v1.5 type-2 tym,
    że ZARAZ PO bajtach wiadomości, przed końcem bloku, wstawia DODATKOWY
    bajt = długość oryginalnego stringa - serwer (RSACipher, zob. docstring
    modułu) odczytuje ten bajt jako znacznik i odrzuca deszyfrowanie, jeśli
    nie zgadza się z długością pozostałych bajtów.

    Układ bloku (k = długość modułu w bajtach):
        0x00 0x02 <k-3-len(msg)-1 losowych, niezerowych bajtów> 0x00
        <bajty wiadomości> <len(wiadomości) jako 1 bajt>
    """
    msg_with_len_marker = message + bytes([len(message)])
    k = (modulus.bit_length() + 7) // 8
    ps_len = k - 3 - len(msg_with_len_marker)
    if ps_len < 8:
        raise ValueError("message too long for this key size")
    ps = bytearray()
    while len(ps) < ps_len:
        b = os.urandom(1)
        if b != b"\x00":
            ps += b
    padded_block = b"\x00\x02" + bytes(ps) + b"\x00" + msg_with_len_marker
    m_int = int.from_bytes(padded_block, "big")
    c_int = pow(m_int, exponent, modulus)
    # Serwer dzieli skonkatenowany string hex na kawałki o STAŁEJ długości
    # (2*k znaków) - krótszy wynik (częste dla liczb z zerowym najwyższym
    # bajtem) trzeba dopełnić zerami z lewej, inaczej kolejne bloki (przy
    # haśle >116 znaków ASCII) rozjeżdżają się o pozycję.
    return format(c_int, "x").zfill(2 * k)


def get_public_key_from_page(path: str) -> str:
    _, body = http_get(path)
    text = body.decode("utf-8", "ignore")
    m = re.search(r'id="publicKey" name="publicKey" value="([0-9a-fA-F]+)"', text)
    if not m:
        raise RuntimeError(f"publicKey field not found on {path}")
    return m.group(1)


def cmd_new_installation():
    """Pierwszy ekran kreatora: 'I'm a server administrator' -> HSQLDB wewnętrzna."""
    status, body = http_get("/mnt")
    print("GET /mnt ->", status, len(body))
    status, body = http_post_form("/mnt/do/goNewInstallation", {"restore": "false"})
    print("POST goNewInstallation ->", status, body[:200])
    status, body = http_post_form("/mnt/do/goNewDatabase", {"dbType": "HSQLDB2"})
    print("POST goNewDatabase ->", status, body[:200])


def cmd_accept_license():
    pubkey_hex = None  # license page doesn't need RSA, just a CSRF token
    _, body = http_get("/mnt")
    text = body.decode("utf-8", "ignore")
    m = re.search(r'name="tc-csrf-token" value="([^"]+)"', text)
    token = m.group(1) if m else ""
    status, body = http_post_form(
        "/showAgreement.html",
        {
            "accept": "true",
            "_accept": "",
            "sendUsageStatistics": "false",
            "_sendUsageStatistics": "",
            "tc-csrf-token": token,
        },
    )
    print("POST showAgreement ->", status, body[:300])


def cmd_create_admin():
    pubkey_hex = get_public_key_from_page("/mnt")
    n = int(pubkey_hex, 16)
    e = 0x10001
    enc_pw1 = pkcs1_pad_encrypt_with_length_marker(ADMIN_PASSWORD.encode("utf-8"), n, e)
    enc_pw2 = pkcs1_pad_encrypt_with_length_marker(ADMIN_PASSWORD.encode("utf-8"), n, e)
    status, body = http_post_form(
        "/createAdminSubmit.html",
        {
            "username1": ADMIN_USER,
            "publicKey": pubkey_hex,
            "encryptedPassword1": enc_pw1,
            "encryptedRetypedPassword": enc_pw2,
            "submitCreateUser": "Create Account",
        },
    )
    print("POST createAdminSubmit ->", status, body[:300])
    # Oczekiwany wynik: b'<response><redirect>/favorite/projects</redirect><errors /></response>'


def cmd_setup_demo_project():
    status, body = rest(
        "POST",
        "/app/rest/projects",
        '<newProjectDescription name="Prasowka Demo"><parentProject locator="id:_Root"/></newProjectDescription>',
    )
    print("create project ->", status, body[:300])

    status, body = rest(
        "POST",
        "/app/rest/vcs-roots",
        """<vcs-root name="Prasowka Demo Root" vcsName="jetbrains.git" id="PrasowkaDemoRoot">
  <project id="PrasowkaDemo"/>
  <properties>
    <property name="url" value="https://github.com/envdev9/newsletter.git"/>
    <property name="branch" value="refs/heads/main"/>
  </properties>
</vcs-root>""",
    )
    print("create vcs-root ->", status, body[:300])

    status, body = rest(
        "POST",
        "/app/rest/projects/id:PrasowkaDemo/projectFeatures",
        """<projectFeature type="VersionedSettings">
  <properties>
    <property name="vcsRootId" value="PrasowkaDemoRoot"/>
    <property name="rootUsedForSync" value="PrasowkaDemoRoot"/>
    <property name="format" value="kotlin"/>
    <property name="buildSettingsMode" value="PREFER_VCS"/>
    <property name="enabled" value="true"/>
    <property name="allowUIEditing" value="true"/>
  </properties>
</projectFeature>""",
    )
    print("enable versioned settings ->", status, body[:300])

    status, body = rest(
        "POST",
        "/app/rest/buildTypes",
        """<buildType name="Release" id="PrasowkaDemo_Release" projectId="PrasowkaDemo">
  <vcs-root-entries>
    <vcs-root-entry><vcs-root id="PrasowkaDemoRoot"/></vcs-root-entry>
  </vcs-root-entries>
</buildType>""",
    )
    print("create build type ->", status, body[:300])

    # Autorytatywne, surowe nazwy parametrów ("teamcity.automerge.*") pochodzą
    # z deskryptora kotlin-dsl/buildFeatures/AutoMerge.xml - zob. README.md.
    status, body = rest(
        "POST",
        "/app/rest/buildTypes/id:PrasowkaDemo_Release/features",
        """<feature type="AutoMergeFeature">
  <properties>
    <property name="teamcity.automerge.srcBranchFilter" value="+:refs/pull/*/head"/>
    <property name="teamcity.automerge.dstBranch" value="refs/heads/main"/>
    <property name="teamcity.merge.policy" value="fastForward"/>
    <property name="teamcity.automerge.buildStatusCondition" value="noNewTests"/>
    <property name="teamcity.automerge.run.policy" value="runBeforeBuildFinish"/>
  </properties>
</feature>""",
    )
    print("add AutoMergeFeature ->", status, body[:400])


def cmd_show_dsl():
    """Realny mechanizm 'Admin -> Versioned Settings -> Show DSL' (prawdziwa
    nazwa akcji w UI: 'Download settings in Kotlin format...'), wywolany
    bezposrednio jako URL znaleziony w HTML strony /admin/editProject.html
    (link do /admin/versionedSettingsActions.html)."""
    url = (
        BASE
        + "/admin/versionedSettingsActions.html?projectId=PrasowkaDemo&action=generate&format=kotlin&version=latest"
    )
    req = urllib.request.Request(url)
    req.add_header("Authorization", _AUTH_HEADER)
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
    out_path = "generated-dsl.zip"
    with open(out_path, "wb") as f:
        f.write(data)
    print(f"Saved {len(data)} bytes to {out_path} (unzip it to see the real, server-generated .kt files)")


COMMANDS = {
    "new-installation": cmd_new_installation,
    "accept-license": cmd_accept_license,
    "create-admin": cmd_create_admin,
    "setup-demo-project": cmd_setup_demo_project,
    "show-dsl": cmd_show_dsl,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: {sys.argv[0]} <{'|'.join(COMMANDS)}>")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()
