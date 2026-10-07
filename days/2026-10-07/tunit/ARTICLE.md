<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #14 — 7 października 2026

![TUnit](https://img.shields.io/badge/TUnit-2EA44F?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-ekspert-8250DF?style=for-the-badge)
![JWKS](https://img.shields.io/badge/JWKS-rotacja_kluczy-D63384?style=for-the-badge)

## TUnit: rotacja kluczy JWT po prawdziwym HTTP i wyścig refresh tokenu — czego nie widać w zielonych testach

</div>

---

> _"Rotacja kluczy zwykle psuje się w jedynym momencie, którego nikt nie testuje: w chwili rotacji."_

W wydaniu #13 jeden serwis podpisywał i weryfikował tokeny RS256, a walidator dostawał klucz
**wpisany na sztywno**. W prawdziwym świecie serwis walidujący jest osobnym procesem, który
**pobiera JWKS od wystawcy przez HTTP**, a wystawca co jakiś czas wymienia klucz. Zostawiliśmy
wtedy otwarte: rotację kluczy z wieloma `kid`, `ConfigurationManager` po HTTP i wyścig przy
równoległym odświeżaniu tokenu. Dziś wszystkie trzy — z liczbami, nie z domysłami.

Sprawdzone: `.NET SDK 10.0.400`, **`TUnit 1.72.16`** (ta sama co w #13, nie sprawdzałem czy jest nowsza),
`Microsoft.AspNetCore.Authentication.JwtBearer 10.0.12`. `dotnet test`: **34/34 testów**, trzy
pełne przebiegi (solution, projekt, filtr), za każdym razem zielono; całość trwa ok. 11 s.

| 🧩 Pytanie | 🏷️ Jak zmierzone | 💡 Wynik |
|---|---|---|
| Co widzi klient w chwili rotacji klucza? | rotacja u wystawcy, potem token z nowym `kid` | stary token: `200`; **pierwszy** token z nowym `kid`: `401`; kolejny: `200` |
| Czy 20 tokenów z wymyślonym `kid` zalewa wystawcę pobraniami JWKS? | licznik pobrań po stronie wystawcy | nie: **2 pobrania łącznie** (1 startowe + 1 wymuszone) |
| Czy wycofany klucz przestaje działać od razu? | `Retire("key-1")` + odświeżenia JWKS | **nie**: 5 pobrań JWKS i nadal `200` przez 4 s; po skróceniu `LastKnownGoodLifetime` do 1 s → `401` po ok. 1,3 s |
| Czy wyścig 32 żądań `/auth/refresh` z jednym tokenem ma jednego zwycięzcę? | `[Repeat]` + bariera | tak (6 przebiegów: zawsze 1 × `200`, 31 × `401`) |
| Czy ten test wyłapie brak `lock` w magazynie? | mutacja: usunięty `lock` | **test HTTP: nie (6/6 zielone)**; test na magazynie z wątkami: **tak (1 na 21 przebiegów padł, `Ok=2`)** |

---

## 1. 🌐 Dwa prawdziwe serwery w jednym teście

Dotąd testy szły przez `WebApplicationFactory` (serwer w pamięci). Tym razem test **uruchamia dwa
prawdziwe serwery Kestrel** na wolnych portach `127.0.0.1` (adres `http://127.0.0.1:0` = „wybierz port
za mnie”, a faktyczny adres czytamy z `app.Urls` po `StartAsync`):

- `IssuerApi` — wystawca: `/auth/login`, `/auth/refresh`, `/.well-known/openid-configuration`,
  `/.well-known/jwks.json`; pierścień kluczy `KeyRing` z wieloma `kid`;
- `ResourceApi` — serwis walidujący: `JwtBearer` z `MetadataAddress` wskazującym na wystawcę. Zero
  kluczy w kodzie — `ConfigurationManager` pobiera dokument metadanych i JWKS po HTTP.

Dzięki temu test sprawdza to, co działa na produkcji: cache, odświeżanie i ruch sieciowy, a nie
atrapę. Licznik `KeyRing.JwksFetches` po stronie wystawcy jest **dowodem ruchu** — nie zgadujemy,
tylko liczymy, ile razy ktoś zapytał o klucze.

> 🎯 **Dlaczego to ważne:** w teście z kluczem wpisanym w konfigurację rotacja nie istnieje. Cała
> klasa błędów (cache, kolejność, okno nakładania) wychodzi dopiero, gdy walidator naprawdę
> pobiera klucze z drugiego procesu.

## 2. 🔁 Rotacja: pierwszy użytkownik z nowym kluczem dostaje 401

Wystawca: `Rotate()` dodaje `key-2` i robi go aktywnym; `key-1` **zostaje w JWKS** (okno nakładania).
Zmierzony przebieg (`ms` = czas pętli odpytującej, nie czas sieci):

```
[pomiar] stary=OK nowy-pierwszy=Unauthorized proby-do-200=2 ms=107 pobrania-JWKS: przed=1 po=2
```

- Stary token (`key-1`) działa — walidator ma go w cache, nic nie pobiera.
- **Pierwsze** żądanie z tokenem podpisanym `key-2` kończy się `401`: walidator nie zna `kid`, więc
  wymusza pobranie JWKS, ale to żądanie już przegrało. Następne (po pobraniu) dostaje `200`.

Czyli przy każdej rotacji **jeden prawdziwy użytkownik (pierwszy trafiający w nowy klucz) dostanie
błąd**, którego wystawca nie widzi w żadnym logu. W tym teście w obu uruchomieniach, które
zmierzyłem, było dokładnie tak (1 odrzucone, potem OK). Jeśli to dla ciebie za dużo: publikuj nowy klucz
w JWKS z wyprzedzeniem i zacznij nim podpisywać dopiero, gdy walidatory zdążą odświeżyć cache
(tego wzorca nie implementowałem w kodzie — to wniosek z pomiaru, nie testowany scenariusz).

> 🎯 **Dlaczego to ważne:** „rotacja bez przestoju” jest bez przestoju tylko dla starych tokenów.
> Test z dwoma `kid` pokazuje dokładny moment, w którym to założenie pęka.

## 3. 🛡️ Zalew nieznanych `kid` nie zalewa wystawcy

Atakujący może wysyłać tokeny z losowym `kid`, licząc, że każdy wymusi pobranie JWKS (atak na
wystawcę przez serwis walidujący). Test wysyła **20** takich tokenów (każdy z innym `kid`):

```
[pomiar] 20 falszywych kid -> pobrania JWKS lacznie=2
```

Wszystkie 20 → `401`, a wystawca dostał **2** żądania JWKS (startowe + jedno wymuszone). Ogranicza to
`RefreshInterval` (domyślnie 5 minut, nie mniej niż 1 s). Zmierzyłem też drugą rotację w obrębie interwału
(3 s w teście): nowy `kid` był odrzucany przez ok. 1,1 s (22 próby), po czym dostał `200`, a pobrań przybył
dokładnie jeden.

⚠️ **Zaskoczenie, którego nie umiem wyjaśnić:** ustawienie `RefreshOnIssuerKeyNotFound = false`
**nie wyłączyło** odświeżenia po nieznanym `kid` — nowy klucz i tak zadziałał po jednym `401` (2 pobrania
JWKS). Oczekiwałem `401` przez cały czas. Test opisuje stan faktyczny na tych wersjach pakietów;
mechanizmu nie badałem (nie czytałem kodu biblioteki), więc nie opieraj na tej fladze bezpieczeństwa.

> 🎯 **Dlaczego to ważne:** bez limitu każdy anonimowy request z wymyślonym `kid` byłby żądaniem do
> wystawcy — gotowy wzmacniacz DoS. Test z licznikiem po stronie wystawcy to jedyny sposób, żeby
> zauważyć, że ktoś ten limit wyłączył.

## 4. 🕳️ Wycofany klucz nadal działa — i to jest główna pułapka tego wydania

Wystawca robi `Rotate()` i od razu `Retire("key-1")` (np. po wycieku klucza). Czy stary token
przestaje działać? Test: odświeżamy JWKS w serwisie walidującym (wymuszamy to tokenem z nieznanym `kid`)
i pytamy o **stary** token:

```
[pomiar] shortLkg=False: zaraz po Retire=OK; po 'wymuszaczu': ostatni=OK proby=73 ms=4007 pobrania-JWKS: przed=1 po=5
```

JWKS został pobrany **pięć razy**, w żadnym nie ma już `key-1`, a stary token **cały czas przechodzi**
(`200` przez wszystkie 4 s obserwacji). Po zmianie jednego ustawienia — `LastKnownGoodLifetime` = 1 s
we własnym `ConfigurationManager` — ten sam scenariusz:

```
[pomiar] shortLkg=True: zaraz po Retire=OK; po 'wymuszaczu': ostatni=Unauthorized proby=21 ms=1290 pobrania-JWKS: przed=1 po=3
```

Interpretacja (hipoteza potwierdzona eksperymentem, ale **kodu biblioteki nie czytałem**): przy
niepowodzeniu walidacji biblioteka sięga po „ostatnią znaną dobrą konfigurację” (*last known good*),
która domyślnie żyje długo — i to ona akceptuje stary klucz. Zmiana tylko tego ustawienia przełączyła
wynik z `200` na `401`, więc to ono decyduje; domyślnej długości życia (nie znam jej dokładnie — nie
mierzyłem) nie podaję jako liczby.

Dwa dodatkowe fakty z pomiaru:

- `AutomaticRefreshInterval` poniżej 5 minut **wywala serwis** (`ArgumentOutOfRangeException: IDX10108`
  → każde żądanie to `500`). Minimum jest `static readonly`, więc w teście nie da się go obejść —
  dlatego scenariusz wycofania wymusza odświeżenie tokenem z nieznanym `kid`, a nie czeka na zegar.
  Pierwsza wersja testu tego nie uwzględniała i dostawała `500` — stąd ten akapit.
- Samo odświeżenie JWKS **nie** wystarcza do unieważnienia klucza po stronie walidatora.

> 🎯 **Dlaczego to ważne:** jeśli „wycofanie” klucza po wycieku polega tylko na usunięciu go z JWKS, atakujący
> z tokenem podpisanym tym kluczem może dalej wchodzić — a wszystkie metryki wystawcy wyglądają poprawnie.
> Tylko test na prawdziwym serwisie walidującym pokazuje różnicę między „wycofałem” a „przestało działać”.

## 5. 🏁 Wyścig `/auth/refresh`: jeden zwycięzca, ale…

Refresh token jest jednorazowy (jak w #13). Co, gdy 32 żądania przyjdą **jednocześnie** z tym samym
tokenem (np. aplikacja mobilna odświeża z kilku miejsc)? Test z barierą (`TaskCompletionSource`),
powtórzony przez `[Repeat(5)]` (daje 6 przebiegów), za każdym razem:

```
[pomiar] 200=1 401=31
```

Skutek uboczny, który test też sprawdza: przegrani przedłożyli **zużyty** token, więc reuse detection
unieważnia **całą rodzinę** — także nowy token zwycięzcy. Uczciwy klient, który wysłał dwa żądania naraz,
zostaje wylogowany. To zachowanie poprawne z punktu widzenia bezpieczeństwa i bolesne z punktu widzenia
UX — warto je znać, zanim ktoś zgłosi „losowe wylogowania”.

> 🎯 **Dlaczego to ważne:** równoległy refresh to realny scenariusz (wiele kart przeglądarki, retry
> w kliencie). Test dokumentuje, że „jedno 200” oznacza też „dwa żądania naraz = wylogowanie”.

## 6. 🧬 Mutacja: test, który przeszedł, a nie powinien

Standardowa metoda z #13: usuń zabezpieczenie i zobacz, czy test padnie. Usunąłem `lock` z
`RefreshTokenStore.Rotate`:

| Test | Przebiegi | Wynik po usunięciu `lock` |
|---|---|---|
| wyścig przez HTTP (Kestrel, 32 żądania) | 6 | **6 zielonych** — mutacja przeżyła |
| wyścig na magazynie (64 wątki + `Barrier`, bez HTTP) | 21 | **1 czerwony** (`Expected to be 1 but found 2`), 20 zielonych |

Test „dowodzący” poprawności przez HTTP **nie wykrywa braku synchronizacji**: żądania przechodzą przez
potok serwera prawie sekwencyjnie, a okno wyścigu jest za wąskie. Dopiero test bez HTTP (bariera na
wątkach, tylko `Rotate`) je trafił — i to raz na 21 prób. Lekcja z wyścigami: **zielony test współbieżności
niczego nie dowodzi**, dopóki nie zobaczysz go czerwonego na mutacji, a pojedynczy przebieg nie wystarcza
(stąd `[Repeat]`). Dodatkowo: nawet 21 powtórzeń złapało błąd raz — to test probabilistyczny, nie
dowód; brak porażki nie gwarantuje braku błędu.

> 🎯 **Dlaczego to ważne:** test wyścigu, który „zawsze przechodzi”, jest gorszy niż brak testu —
> daje fałszywe poczucie bezpieczeństwa. Mutacja to jedyny sposób, by to sprawdzić.

## 7. 🧪 Nowe w TUnit

- **`[Repeat(n)]`** — test uruchamiany `n+1` razy (zmierzone: `[Repeat(5)]` → 6 wyników, `[Repeat(20)]` → 21).
  Każde powtórzenie jest osobnym wynikiem w raporcie, więc jedna czerwona z 21 jest widoczna.
- **`[Arguments(...)]` z `[DisplayName]`** (`$shortLkg`, `$expected`) — tu użyte do jednego testu na dwa warianty
  konfiguracji; nazwa w wyniku zawiera wartości argumentów.
- **`using (Assert.Multiple()) { ... }`** — w TUnit 1.72.16 `Assert.Multiple()` zwraca zasób `IDisposable`
  (próba przekazania lambdy: `CS1501: No overload for method 'Multiple' takes 1 arguments`). Kilka asercji
  zgłasza wspólnie wszystkie porażki naraz, a nie tylko pierwszą.
- **Własna pętla odpytująca zamiast `Task.Delay`** (`PollUntilAsync`): test czeka tylko tyle, ile
  trzeba, i zwraca liczbę prób i czas — te liczby są w artykule.

## ✅ Co zweryfikowano, a co nie

- ✔️ `dotnet test`: **34/34** (7 testów rotacji + 6 wyścigu HTTP + 21 wyścigu na magazynie), TUnit 1.72.16, .NET SDK
  10.0.400, net10.0 — przebieg projektu (dwa razy) i solution (`KeyRotation.slnx`), wszystkie zielone;
  czas ok. 10–11 s.
- ✔️ Wszystkie liczby w tabeli na górze są z realnych przebiegów (cytowane linie `[pomiar]` pochodzą z
  `--output Detailed`; `ms` różni się między przebiegami — traktuj jako rząd wielkości, nie stałą).
- ✔️ Mutacja `lock`: test HTTP nie wykrył, test na magazynie wykrył (1/21). Po mutacji kod przywrócony
  (ostatni pełny przebieg 34/34 był już po przywróceniu).
- ⚠️ Zmierzone, ale **bez wyjaśnionego mechanizmu**: (a) `RefreshOnIssuerKeyNotFound = false` nie
  wyłączył odświeżania; (b) stary klucz dalej akceptowany po odświeżeniu JWKS — przypisuję to
  *last known good* (zmiana `LastKnownGoodLifetime` odwróciła wynik), ale kodu biblioteki nie czytałem.
- ⚠️ `dotnet test <ścieżka>.csproj` (bez `--project`) **nie działa** na .NET 10 SDK dla projektu MTP bez
  odpowiedniego `global.json`: `error: Testing with VSTest target is no longer supported by
  Microsoft.Testing.Platform on .NET 10 SDK` (zmierzone). `dotnet test --project …` z katalogu bez
  `global.json` kończy się `MSB1001: Unknown switch`. Obejście zastosowane w tej sesji: tymczasowy
  `global.json` w katalogu **powyżej** repo (poza repo; nie dało się go usunąć — `rm` odrzucone). Dla
  czytelnika: uruchamiaj z `code/`, gdzie leży `global.json`.
- ⚠️ **Niezweryfikowane:** domyślna wartość `LastKnownGoodLifetime`; rotacja z wyprzedzeniem (publikacja klucza
  przed podpisywaniem nim) jako sposób na uniknięcie pierwszego `401`; zachowanie przy dłuższym działaniu
  (godziny, `AutomaticRefreshInterval` 12 h — niemożliwe do przeczekania, a minimum 5 min nie da się skrócić);
  wiele instancji wystawcy z osobnymi pierścieniami kluczy; RS256 z certyfikatem X.509 (rubryka o
  certyfikatach); SDK inne niż 10.0.400; działanie pod obciążeniem CI (testy z czasem mogą być
  wolniejsze — pętle mają limity 3–20 s).
- ⚠️ Czas realny, nie `FakeTimeProvider`: tokeny dostępu żyją 10 minut, a testy nie przesuwają zegara (inaczej
  niż w #13) — `ConfigurationManager` korzysta z zegara systemowego i nie dało się go tu podmienić.
- ⚠️ Artefakty: w `RotationTests/` został pusty plik `ScratchTests.cs` (po sondzie pomiarowej; `rm`
  odrzucone) — do ręcznego skasowania. `bin/`, `obj/` wykluczone przez `code/.gitignore`.

**Pełny, uruchamialny przykład:** [`code/`](code/) — solution [`KeyRotation.slnx`](code/KeyRotation.slnx).

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md) — komendy + prawdziwy output `dotnet test`.

---

<div align="center">

[← wróć do wydania #14 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
