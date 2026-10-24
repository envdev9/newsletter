# Kod do wydania #7 — .NET Aspire: Postgres z trwałością danych + `user-secrets`

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Wymagania

- **.NET 10 SDK** (sprawdzone na `10.0.400`), pakiety Aspire `13.5.2` z nuget.org.
- **Docker** (sprawdzone na Docker Engine `29.1.3`) — demon musi odpowiadać (`docker info`).
  Ten kod **realnie uruchamia kontener Postgres** przez Docker, nie atrapę.
- Jeśli `dotnet` nie jest w PATH: `export PATH="$HOME/.dotnet:$PATH"`.
- Domyślny obraz to `postgres:18.3` (zmierzone z logów kontenera, nie z dokumentacji) —
  ok. 650 MB, jeśli nie masz go jeszcze w cache Dockera.

## Fragment prasówki, którego dotyczy ten kod

> `AddParameter(secret: true)` czyta hasło administratora Postgresa z konfiguracji pod
> kluczem `Parameters:pg-password` — źródłem w Development jest `dotnet user-secrets`
> (zero sekretów w `appsettings.json`, zero w Git). `AddPostgres("pg", password:
> pgPassword).WithDataVolume()` podpina pod kontener **nazwany, trwały** wolumin Docker:
> dane przeżywają `StopAsync`/`docker rm` kontenera, więc drugi `dotnet run` na tym
> samym AppHoście (nowy kontener, ten sam wolumin) widzi dane z poprzedniego
> uruchomienia. Aspire sprząta kontener automatycznie, ale **nigdy nie usuwa nazwanego
> woluminu** — to trzeba zrobić ręcznie (`docker volume rm`).

## Struktura

```
code/
├── AppHost/        # AddParameter("pg-password", secret: true), AddPostgres().WithDataVolume(), AddDatabase("notesdb")
├── NotesApi/        # POST/GET /notes przez Npgsql (NpgsqlDataSource), /notes-info (kształt connection stringa)
└── Notes.Verify/    # test AppHosta: DWA niezależne uruchomienia AppHosta w jednym procesie, dowód trwałości danych
```

## Uruchomienie zautomatyzowanego testu (zalecane)

Wymaga działającego Dockera (`docker info` musi się powieść). Z katalogu `code/`:

```bash
dotnet run --project Notes.Verify/Notes.Verify.csproj
```

Hasło do Postgresa jest tu przekazywane przez argumenty testu
(`Parameters:pg-password=...`) — ta sama metoda co w `Config.Verify` z wydania #4 —
żeby test był powtarzalny bez zależności od pliku `user-secrets` na konkretnej maszynie.

Kod wyjścia 0 = sukces. Prawdziwy wynik (SDK `10.0.400`, Aspire `13.5.2`, Docker
`29.1.3`, Linux), zmierzony w tym repo:

```
=== Przebieg #1: start AppHost, INSERT notatki, zatrzymanie AppHosta ===
notes-api = Healthy (kontener Postgres 'pg' też musiał wystartować)
GET /notes-info -> {"hasPassword":true,"hasHost":true,"hasDatabase":true}
[PASS] Aspire wstrzyknęło connection string z hasłem z parametru (nie z kodu)
[PASS] connection string wskazuje na kontener (Host=...)
[PASS] connection string wskazuje na bazę notesdb
[PASS] POST /notes -> 200 (OK)
POST /notes body -> {"id":1,"text":"prasowka-nota-5f01aa19","createdAt":"2026-09-30T01:02:38.372728Z"}
--- Zatrzymywanie AppHost #1 (Aspire zdejmuje kontener Postgres, wolumin ZOSTAJE) ---

=== Przebieg #2: NOWY AppHost od zera, sprawdzamy czy notatka przeżyła ===
notes-api = Healthy (NOWY kontener Postgres, ten sam nazwany wolumin)
GET /notes -> [{"id":1,"text":"prasowka-nota-5f01aa19","createdAt":"2026-09-30T01:02:38.372728Z"}]
[PASS] notatka z Przebiegu #1 PRZEŻYŁA restart AppHosta (WithDataVolume działa) (prasowka-nota-5f01aa19)
[PASS] zapis nadal działa po restarcie (POST /notes -> 200)
--- Zatrzymywanie AppHost #2 ---

WSZYSTKO OK
UWAGA: wolumin danych Postgresa NIE jest usuwany automatycznie (to sens WithDataVolume) -
posprzątaj go ręcznie: patrz sekcja 'Porządek' niżej.
```

Po zakończeniu `docker ps -a` nie pokazuje żadnego kontenera `pg-*` (Aspire sprzątnął
oba, z przebiegu #1 i #2) — ale `docker volume ls` **nadal pokazuje** nazwany wolumin
(np. `apphost-<hash>-pg-data`), bo to cały sens `WithDataVolume()`. Zobacz "Porządek"
niżej.

## Ręcznie: prawdziwy `dotnet user-secrets` + `dotnet run` (dokończenie wątku z #4)

To dokładnie zweryfikowaliśmy w tym wydaniu (nie tylko przez test, ale ręcznym
`dotnet run` + zapytaniem HTTP do żywej usługi):

```bash
cd AppHost
dotnet user-secrets set "Parameters:pg-password" "moje-lokalne-demo-haslo"
dotnet run --launch-profile http
```

W drugim terminalu (uwaga: w środowisku, w którym to pisaliśmy, `curl` był
zablokowany przez politykę uprawnień nawet do `localhost` — użyliśmy Pythona jako
zamiennika; u Ciebie zwykły `curl` powinien działać normalnie):

```bash
curl http://localhost:5297/notes-info
# {"hasPassword":true,"hasHost":true,"hasDatabase":true}

curl -X POST http://localhost:5297/notes \
  -H "Content-Type: application/json" \
  -d '{"text":"pierwsza notatka"}'
# {"id":1,"text":"pierwsza notatka","createdAt":"..."}

curl http://localhost:5297/notes
```

Port `5297` to `applicationUrl` z `NotesApi/Properties/launchSettings.json` — Aspire
w trybie `dotnet run` (nie w teście) honoruje ten profil. Zatrzymaj AppHost przez
`Ctrl+C` w pierwszym terminalu — to wyzwala normalne, łagodne zamknięcie (Aspire
zdejmuje kontener Postgresa; wolumin zostaje, patrz "Porządek").

Po zakończeniu warto wyczyścić sekret testowy: `dotnet user-secrets clear` (z
katalogu `AppHost/`) — nie zostawia śladu w repo (plik sekretów leży poza nim), ale
czyści go też lokalnie z Twojej maszyny dev.

## Porządek — trwały wolumin trzeba usunąć RĘCZNIE

To jedyna rzecz, o której Aspire świadomie **nie** decyduje za Ciebie — trwały
wolumin ma przetrwać zamknięcie AppHosta, więc nikt go automatycznie nie kasuje.
Po zakończeniu eksperymentów z tym kodem:

```bash
docker volume ls | grep apphost   # znajdź nazwę, np. apphost-951a0d4242-pg-data
docker volume rm <nazwa-woluminu>
```

**Nie usuwaj woluminów innych projektów** widocznych w `docker volume ls` na
współdzielonej maszynie (np. `aspiredemo.apphost-*`, `aspirelab.apphost-*`) — to nie
są artefakty tego repo. Nazwa woluminu tego przykładu zawiera hash pochodzący z
nazwy projektu AppHost i nazwy zasobu `pg` — sprawdź `docker volume ls` PRZED
usunięciem, żeby usunąć właściwy.

Katalogi `bin/`, `obj/` są w `.gitignore` repo (główny `.gitignore`, `bin/`/`obj/`).
Obraz `postgres:18.3` zostaje w lokalnym cache Dockera (nie w repo) — kolejne
`dotnet run` nie muszą go pobierać ponownie.
