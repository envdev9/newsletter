<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #4 — 27 września 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-średnio_zaawansowany-orange?style=for-the-badge)

## Parametry, sekrety i `WithEnvironment`: co dokładnie dostaje Twój proces

</div>

---

> _"`AddParameter("x", "wartość")` wygląda jak parametr z wartością domyślną. Nie jest.
> To stała — konfiguracja nawet nie zostanie zapytana."_

Do tej pory AppHost mówił *co* uruchomić. Dziś mówi, **z jakimi danymi**: hasła, klucze,
tryby pracy. Aspire ma na to jeden mechanizm — `AddParameter` + `WithEnvironment` — i kilka
pułapek, o których dokumentacja wspomina półgłosem. Wszystko poniżej zweryfikowane realnym
uruchomieniem (`.NET SDK 10.0.400`, `Aspire 13.5.2`, Linux). Kod: [`code/`](code/).

**Docker:** demon odpowiada, ale nie mamy tu pobranych obrazów, więc **celowo zostajemy bez
kontenerów** (Postgres/Redis — w kolejnym wydaniu, gdy bezpiecznie będzie pobrać obraz).
Parametry i `WithEnvironment` kontenerów nie potrzebują.

---

### 1. `AddParameter`: trzy formy, jedna z nich podstępna

```csharp
var greeting  = builder.AddParameter("greeting");                    // z konfiguracji
var fixedText = builder.AddParameter("fixed-text", "stała z kodu");  // STAŁA!
var apiKey    = builder.AddParameter("api-key", secret: true);       // sekret z konfiguracji
```

| Forma | Skąd wartość | Co gdy brak |
|---|---|---|
| `AddParameter("nazwa")` | konfiguracja `Parameters:nazwa` | stan zasobu `ValueMissing` |
| `AddParameter("nazwa", secret: true)` | j.w. + oznaczenie jako sekret | j.w. |
| `AddParameter("nazwa", "wartość")` | **wartość z kodu** | — (nie ma czego brakować) |

Konfiguracja `Parameters:*` to zwykła konfiguracja .NET, więc wartość może przyjść z
user-secrets, zmiennej `Parameters__api-key` albo argumentu wiersza poleceń. My w teście
podajemy argumenty (`Parameters:api-key=...`).

**Pułapka (zmierzona).** Przekazaliśmy `Parameters:fixed-text=z konfiguracji`, a proces
dostał i tak `"stała z kodu"`:

```
"greeting":"Witaj","fixedText":"stała z kodu"
[PASS] AddParameter(nazwa): GREETING == Witaj (z Parameters:greeting)
[PASS] AddParameter(nazwa, wartość) jest STAŁE: FIXED_TEXT ignoruje konfigurację
```

Czyli przeciążenie z wartością **nie jest** "domyślną z możliwością nadpisania". Jeśli
chcesz nadpisywalną domyślną, musisz ją sam złożyć z `builder.Configuration`.
(To zachowanie 13.5.2; przeciążenia mogą się zmienić.)

### 2. `WithEnvironment` — trzy przeciążenia w jednym zasobie

```csharp
builder.AddProject<Projects.ConfigApi>("config-api")
    .WithEnvironment("APP_MODE", "demo")                 // literał
    .WithEnvironment("GREETING", greeting)               // parametr
    .WithEnvironment("API_KEY", apiKey)                  // sekret, ta sama składnia
    .WithEnvironment("DB_CONNECTION",                    // wyrażenie z parametrów
        ReferenceExpression.Create($"Host=db.local;Database=shop;Password={dbPassword}"))
    .WithEnvironment(ctx =>                              // callback
    {
        ctx.EnvironmentVariables["RUN_MODE"] = ctx.ExecutionContext.IsRunMode ? "run" : "publish";
    });
```

- **`ReferenceExpression`** składa wartość z kawałków, z których część to parametry —
  Aspire rozwiąże je leniwie, a w manifeście publikacji zamieni na referencje zamiast
  wartości. Nie sklejaj sekretów zwykłym `string.Format` w AppHost.
- **Callback** daje dostęp do `ExecutionContext` — ta sama definicja może zachowywać się
  inaczej lokalnie (`IsRunMode`) i przy publikacji.

Prawdziwa odpowiedź z endpointu `/env` procesu `config-api` (sekret zamaskowany po
stronie serwisu — długość i skrót SHA-256, nigdy wartość):

```
{"appMode":"demo","greeting":"Witaj","fixedText":"stała z kodu","runMode":"run",
 "apiKey":"len=14;sha256=953A6F3A","dbConnectionPrefix":"Host=db.local;Database=shop;",
 "dbConnectionHasPassword":true}
```

### 3. `AddExecutable` — dowolny proces w orkiestracji

Nie wszystko jest projektem .NET. `AddExecutable(nazwa, polecenie, katalog, argumenty...)`
uruchamia cokolwiek i pozwala wstrzyknąć te same parametry:

```csharp
builder.AddExecutable("env-printer", "sh", ".",
        "-c", "echo \"env-printer: GREETING=$GREETING KEY_LEN=${#API_KEY}\"; sleep 2")
    .WithEnvironment("GREETING", greeting)
    .WithEnvironment("API_KEY", apiKey);
```

Log tego procesu odczytujemy z kodu przez `ResourceLoggerService.WatchAsync(zasób)`:

```
log env-printer -> 2026-09-27T00:45:08.9520000Z env-printer: GREETING=Witaj KEY_LEN=14
[PASS] AddExecutable dostał GREETING i sekret (KEY_LEN)
```

(Uwaga praktyczna: log widać jako `[sys] Starting process...: Cmd = /usr/bin/sh, Args = [...]`
— Aspire loguje pełną komendę, więc nie wkładaj sekretów do *argumentów*; do środowiska tak.)

### 4. Co się dzieje, gdy sekretu brakuje

Scenariusz B: ten sam AppHost, ale bez `Parameters:api-key`. Obserwowane stany zasobów:

```
  stan: api-key=ValueMissing
  stan: config-api=FailedToStart
  stan: env-printer=FailedToStart
```

W logu Aspire pojawia się `MissingParameterValueException: Parameter resource could not be
used because configuration key 'Parameters:api-key' is missing and the Parameter has no
default value.` Zasoby zależne od parametru **nie startują** — to dobre zachowanie
("fail fast"), nie ciche uruchomienie z pustym kluczem. Zasób bez tego parametru
(gdybyśmy takiego mieli) wstałby normalnie.

### 5. Test AppHosta jako weryfikacja konfiguracji

`Config.Verify` (jak `Store.Verify` z #3) podnosi AppHost w procesie i sprawdza
wszystko `HttpClient`em. Nowość: **argumenty** w `CreateAsync<Projects.AppHost>(args)`
podają parametry, więc jeden AppHost przetestujesz w wariancie "jest sekret" i "brak sekretu":

```csharp
var appHost = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
    ["Parameters:api-key=test-key-12345", "Parameters:db-password=p@ss-987", ...], ct);
```

(Wartości to atrapy testowe, nie prawdziwe sekrety.) Jedno polecenie:

```bash
dotnet run --project days/2026-09-27/aspire/code/Config.Verify/Config.Verify.csproj
```

Wynik (poziom logów zredukowany argumentem `Logging:LogLevel:Default=Warning`, poza
`env-printer`, żeby było widać jego linię):

```
=== A: parametry podane ===
[PASS] literał: APP_MODE == demo
[PASS] AddParameter(nazwa): GREETING == Witaj (z Parameters:greeting)
[PASS] AddParameter(nazwa, wartość) jest STAŁE: FIXED_TEXT ignoruje konfigurację
[PASS] callback WithEnvironment(ctx): RUN_MODE == run
[PASS] sekret dotarł do procesu (długość i skrót się zgadzają)
[PASS] ReferenceExpression złożył connection string
[PASS] AddExecutable dostał GREETING i sekret (KEY_LEN)
=== B: brak Parameters:api-key ===
[PASS] brak sekretu -> config-api NIE jest Running/Healthy (api-key=ValueMissing, config-api=FailedToStart, env-printer=FailedToStart)
WSZYSTKO OK
```

### Dlaczego to ważne w praktyce

1. **Jedna pułapka `AddParameter(nazwa, wartość)` = "nadpisuję z CI, a nic się nie dzieje".**
   Teraz wiesz, dlaczego.
2. **Fail fast dla brakujących sekretów** — `ValueMissing` zamiast aplikacji z pustym kluczem.
3. **`ReferenceExpression`** to droga do connection stringów, które w przyszłości wskażą
   na kontener bazy bez zmiany kodu serwisu — dziś tylko jego "kształt".
4. **Testowalna konfiguracja**: warianty parametrów sprawdzasz w CI bez Dockera.

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Kontenery** (Postgres/Redis) — pominięte celowo, patrz wyżej.
- **`dotnet user-secrets`** i podpowiedź parametrów w dashboardzie (interaktywne
  uzupełnianie brakujących wartości) — użyliśmy tylko argumentów wiersza poleceń.
- **Maskowanie sekretów w dashboardzie** i w manifeście publikacji — nie otwieraliśmy
  dashboardu ani nie robiliśmy `publish`. Nie zakładaj, że `secret: true` chroni sekret przed
  zmienną środowiskową widoczną dla procesu (proces ją oczywiście dostaje).
- Czy wartość `secret: true` pojawia się w logach Aspire — nie przeszukiwaliśmy logów pod tym kątem.
- `appsettings.json` AppHosta jako źródło `Parameters:*` przy zwykłym `dotnet run`
  (w teście używamy argumentów; wcześniejsza próba z appsettings w ścieżce testowej nie zadziałała
  jak zakładaliśmy i nie badaliśmy przyczyny).
- Tylko Linux, HTTP, Aspire 13.5.2.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md).

---

<div align="center">

[← wydanie #4 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
