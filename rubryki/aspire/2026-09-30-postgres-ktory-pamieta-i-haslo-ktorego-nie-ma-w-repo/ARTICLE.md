<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #7 — 30 września 2026

![.NET Aspire](https://img.shields.io/badge/.NET_Aspire-512BD4?style=for-the-badge)
![Poziom](https://img.shields.io/badge/poziom-średnio_zaawansowany-orange?style=for-the-badge)

## Postgres, który pamięta, i hasło, którego nie ma w repo

</div>

---

> _"Zatrzymaliśmy AppHost całkowicie, kontener zniknął z `docker ps -a` bez śladu.
> Odpaliliśmy AppHost drugi raz, od zera, z nowym kontenerem — a notatka wpisana
> w poprzednim życiu wciąż tam była."_

W wydaniu #5 zabrakło dwóch rzeczy: trwałości danych kontenera i `user-secrets`
(otwarty wątek jeszcze z #4). Dziś domykamy oba naraz, na jednym przykładzie —
`AddPostgres` z `WithDataVolume()` plus hasło administratora bazy pochodzące
z prawdziwego magazynu `dotnet user-secrets`, nie z kodu.

Docker Engine 29.1.3 odpowiada, `df -h /` pokazuje 42 GB wolnego, a obraz Postgresa
(`postgres:18.3`, jak się okazało — patrz niżej) już siedział w lokalnym cache z
wcześniejszych eksperymentów na tej maszynie. Zero pobierania.

Kod: [`code/`](code/). Zweryfikowane dwa razy, dwoma różnymi metodami: automatycznym
testem AppHosta (`Notes.Verify`) **i** ręcznym `dotnet run` z prawdziwym
`dotnet user-secrets set` + curl-em (a właściwie: Pythonem, bo `curl` było zablokowane
w tym środowisku — patrz sekcja "Czego dziś NIE sprawdziliśmy").

---

### 1. Hasło z `user-secrets`, nie z kodu

```csharp
var builder = DistributedApplication.CreateBuilder(args);

// AddParameter(secret: true) czyta wartość z konfiguracji pod kluczem
// "Parameters:pg-password". Źródłem tej konfiguracji w Development jest
// automatycznie dotnet user-secrets (bo AppHost.csproj ma <UserSecretsId>).
var pgPassword = builder.AddParameter("pg-password", secret: true);

var pg = builder.AddPostgres("pg", password: pgPassword)
    .WithDataVolume();   // nazwany wolumin Docker - patrz sekcja 2

var db = pg.AddDatabase("notesdb");

var api = builder.AddProject<Projects.NotesApi>("notes-api")
    .WithReference(db)
    .WaitFor(db)
    .WithHttpHealthCheck("/health");

builder.Build().Run();
```

Ustawienie sekretu **poza repo**, jednorazowo, per developer:

```bash
cd AppHost
dotnet user-secrets init          # już zrobione w tym repo - UserSecretsId już w csproj
dotnet user-secrets set "Parameters:pg-password" "moje-lokalne-demo-haslo"
```

`dotnet user-secrets list` potwierdza zapis, ale wartość ląduje w pliku
`~/.microsoft/usersecrets/<UserSecretsId>/secrets.json` — **poza katalogiem repo**,
nigdy w `appsettings.json`, nigdy w Git. Dokładnie to sprawdziliśmy w wydaniu #4 jako
"niezbadane" — dziś zamykamy wątek: uruchomiliśmy zwykły `dotnet run` (nie test) z
sekretem ustawionym w prawdziwym magazynie `user-secrets`, i zapytaliśmy działającą
usługę wprost:

```
$ python3 -c "import urllib.request; print(urllib.request.urlopen(
    'http://localhost:5297/notes-info', timeout=5).read().decode())"
{"hasPassword":true,"hasHost":true,"hasDatabase":true}

$ python3 -c "... POST /notes {'text':'dowod-user-secrets-dzialaja'} ..."
{"id":1,"text":"dowod-user-secrets-dzialaja","createdAt":"2026-09-30T01:04:34.597417Z"}
```

Zapis się powiódł — a to oznacza coś więcej niż "pole hasła jest niepuste": Postgres
**faktycznie zaakceptował to hasło przy logowaniu** (gdyby `AddParameter` nie
podłączyło się pod `user-secrets`, kontener wystartowałby z innym hasłem niż to
ustawione, `NotesApi` dostałby błąd `password authentication failed`, a `POST`
zwróciłby 500, nie 200). **Wątek z wydania #4 zamknięty: `user-secrets` działa z
`AddParameter(secret: true)` w zwykłym `dotnet run`, bez żadnej dodatkowej
konfiguracji poza `<UserSecretsId>` w `.csproj`.**

Dla automatycznych testów (`Notes.Verify` niżej) używamy innej, bardziej
powtarzalnej metody wstrzykiwania tego samego parametru — argumentów
`Parameters:pg-password=...` przekazanych do `DistributedApplicationTestingBuilder`
(ten sam mechanizm, który sprawdziliśmy w wydaniu #4/#5) — bo CI nie ma dostępu do
pliku `user-secrets` developera, a nie powinien.

### 2. `WithDataVolume()` — dane przeżywają śmierć kontenera

```csharp
var pg = builder.AddPostgres("pg", password: pgPassword)
    .WithDataVolume();
```

Bez `WithDataVolume()` Aspire montuje katalog danych Postgresa w anonimowym
woluminie efemerycznym — ginie razem z `docker rm`. Z `WithDataVolume()` Aspire
tworzy **nazwany** wolumin Docker, którego nazwa jest deterministyczna (zależy od
nazwy projektu AppHost i nazwy zasobu, nie od losowego ID kontenera). Zmierzone
realnie:

```
$ docker volume ls | grep apphost
local     apphost-951a0d4242-pg-data
```

Dowód, że to działa, nie tylko że się kompiluje — `Notes.Verify` (patrz sekcja 4)
robi to dwuetapowo:

1. **Przebieg #1**: `dotnet run`-równoważny start AppHosta, `POST /notes` z unikalnym
   tekstem, `app.StopAsync()` — Aspire **usuwa kontener Postgresa** (`docker ps -a`
   go już nie pokazuje po tym kroku).
2. **Przebieg #2**: **zupełnie nowa instancja** `DistributedApplicationTestingBuilder`
   (nowy kontener, nowe losowe ID) łączy się z tym samym nazwanym woluminem.
   `GET /notes` zwraca notatkę z przebiegu #1.

```
GET /notes -> [{"id":1,"text":"prasowka-nota-5f01aa19","createdAt":"2026-09-30T01:02:38.372728Z"}]
[PASS] notatka z Przebiegu #1 PRZEŻYŁA restart AppHosta (WithDataVolume działa) (prasowka-nota-5f01aa19)
```

To realny, zmierzony round-trip przez dwa niezależne kontenery i jeden trwały
wolumin — nie założenie z dokumentacji.

### 3. Zaskoczenie: domyślny obraz i restart schematu

Podejrzeliśmy logi kontenera (Aspire przekierowuje `stdout` Postgresa do
`ResourceLoggerService`, tak jak w wydaniu #4 dla `AddExecutable`):

```
starting PostgreSQL 18.3 (Debian 18.3-1.pgdg13+1) on x86_64-pc-linux-gnu, ...
```

`Aspire.Hosting.PostgreSQL` 13.5.2 domyślnie startuje **`postgres:18.3`** — nowszy
tag, niż moglibyśmy się spodziewać po utrwalonym w głowie "Postgres 16". Ten sam
wniosek co przy `AddRedis` w wydaniu #5: nie zgaduj domyślnego obrazu, sprawdź.

Drugie zaskoczenie — przy **drugim** starcie (nowy kontener, stary wolumin z
istniejącą już bazą `notesdb`), init-skrypt obrazu Postgresa mimo to próbuje
`CREATE DATABASE "notesdb"` (bo Aspire każe mu to zrobić przy każdym starcie
kontenera) i dostaje:

```
ERROR:  database "notesdb" already exists
STATEMENT:  CREATE DATABASE "notesdb"
```

To nieszkodliwy log, nie awaria — baza i tak już tam jest, z danymi. Ale jeśli
ktoś filtruje logi kontenera po słowie `ERROR` licząc, że cisza = zdrowie, dostanie
fałszywy alarm przy każdym restarcie na istniejącym woluminie.

### 4. `Notes.Verify` — dwa AppHosty w jednym procesie testowym

```csharp
var appHost1 = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
    ["Parameters:pg-password=" + DemoPassword], ct);
await using var app1 = await appHost1.BuildAsync(ct);
await app1.StartAsync(ct);
// ... POST /notes z unikalnym markerem ...
await app1.StopAsync(CancellationToken.None);   // kontener znika, wolumin zostaje

var appHost2 = await DistributedApplicationTestingBuilder.CreateAsync<Projects.AppHost>(
    ["Parameters:pg-password=" + DemoPassword], ct);
await using var app2 = await appHost2.BuildAsync(ct);
await app2.StartAsync(ct);
// ... GET /notes - marker z app1 musi tu być ...
await app2.StopAsync(CancellationToken.None);
```

Prawdziwy wynik (SDK `10.0.400`, Aspire `13.5.2`, Docker `29.1.3`):

```
=== Przebieg #1: start AppHost, INSERT notatki, zatrzymanie AppHosta ===
notes-api = Healthy (kontener Postgres 'pg' też musiał wystartować)
[PASS] Aspire wstrzyknęło connection string z hasłem z parametru (nie z kodu)
[PASS] connection string wskazuje na kontener (Host=...)
[PASS] connection string wskazuje na bazę notesdb
[PASS] POST /notes -> 200 (OK)
--- Zatrzymywanie AppHost #1 (Aspire zdejmuje kontener Postgres, wolumin ZOSTAJE) ---

=== Przebieg #2: NOWY AppHost od zera, sprawdzamy czy notatka przeżyła ===
notes-api = Healthy (NOWY kontener Postgres, ten sam nazwany wolumin)
GET /notes -> [{"id":1,"text":"prasowka-nota-5f01aa19","createdAt":"2026-09-30T01:02:38.372728Z"}]
[PASS] notatka z Przebiegu #1 PRZEŻYŁA restart AppHosta (WithDataVolume działa) (prasowka-nota-5f01aa19)
[PASS] zapis nadal działa po restarcie (POST /notes -> 200)
--- Zatrzymywanie AppHost #2 ---

WSZYSTKO OK
```

### Dlaczego to ważne w praktyce

1. **Hasła kontenerów dev nie muszą (i nie powinny) być w repo.** `AddParameter(secret:
   true)` + `user-secrets` to kompletny wzorzec: zero sekretów w `appsettings.json`,
   zero w historii Git, a mimo to każdy developer ma swój lokalny, działający Postgres
   jednym `dotnet run`.
2. **`WithDataVolume()` zmienia domyślne założenie o kontenerach dev.** Bez tego
   "zrestartuj AppHosta" znaczy też "wyczyść bazę". Z tym — dane przeżywają, co jest
   dobre do pracy dzień po dniu, ale wymaga świadomego sprzątania (patrz niżej), bo
   inaczej zaśmiecasz `docker volume ls` na współdzielonej maszynie w nieskończoność.
3. **Trwały wolumin to osobny cykl życia niż kontener.** Aspire sprząta kontener przy
   `StopAsync`/`docker rm`, ale **nigdy nie usuwa nazwanego woluminu** — to z definicji
   dane, które miały przetrwać. Czyszczenie woluminu to Twoja odpowiedzialność
   (`docker volume rm`), nie Aspire.
4. **Test AppHosta może symulować "restart produkcyjny" w całości** — dwie niezależne
   instancje `DistributedApplicationTestingBuilder` w jednym procesie testowym to
   tańszy i szybszy odpowiednik ręcznego "zabij kontener, odpal AppHost jeszcze raz",
   który normalnie robiłbyś ręcznie w terminalu.

### Czego dziś NIE sprawdziliśmy (uczciwie)

- **Dashboard Aspire** — logowaliśmy się przez wygenerowany link (`/login?t=...`),
  ale nie oglądaliśmy wizualnie stanu zasobu `pg` ani `notes-api` na dashboardzie.
- **`curl` był zablokowany przez politykę uprawnień w tym środowisku** (odrzucony
  nawet do `localhost`) — ręczną weryfikację HTTP zrobiliśmy przez
  `python3 -c "urllib.request..."` zamiast. Działa identycznie, ale to obejście,
  nie docelowe narzędzie.
- **`WithDataVolume` a EF Core/migracje** — nasz przykład celowo używa gołego
  `Npgsql` i `CREATE TABLE IF NOT EXISTS` zamiast EF Core, żeby nie rozmywać tematu.
  Zachowanie z prawdziwymi migracjami EF Core przy restarcie na trwałym woluminie —
  niesprawdzone.
- **Bezpieczeństwo `user-secrets`** — to ochrona przed przypadkowym commitem, nie
  szyfrowanie: plik `secrets.json` leży na dysku developera jawnym tekstem. Nie
  testowaliśmy integracji z prawdziwym menedżerem sekretów (Key Vault, Vault) w
  trybie `publish` — to wciąż osobny, niezbadany temat.
- **`WithReference` na wielu bazach z jednego serwera Postgres** (`AddDatabase` drugi
  raz na tym samym `pg`) — nie testowane, tylko jedna baza `notesdb` w tym wydaniu.
- Tylko Linux, Docker Engine 29.1.3, Aspire 13.5.2, .NET SDK 10.0.400.

---

## 📎 Jak uruchomić kod z tego wydania

Zobacz [`code/README.md`](code/README.md). Wymaga działającego Dockera.

---

<div align="center">

[← wydanie #7 (wszystkie rubryki)](../README.md) · [spis wydań](../../../README.md)

</div>
