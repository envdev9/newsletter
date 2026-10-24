# Kod do wydania #17 — prompty do dokumentacji (XML-doc, README, ADR) z walidatorem zgodności z kodem

Pełny artykuł: [`../ARTICLE.md`](../ARTICLE.md).

## Fragment prasówki, którego dotyczy ten kod

> Dokumentacja z modelu zmyśla (parametr, wyjątek, „jitter") albo starzeje się po cichu. Lekarstwo:
> fakty o kodzie (parametry, wyjątki z ciała metody, stałe) wchodzą do promptu **ze skryptu**
> (`docs_check.py facts`), model pisze dokument w wąskim, sprawdzalnym formacie, a ten sam skrypt
> (`docs_check.py check`) waliduje wynik. Na 11 wprowadzonych rozjazdów walidator złapał 9, kompilator
> (XML-doc) 2, a wykonywane przykłady (`Retry.Demo`) 4; walidator + przykłady razem 11/11. Walidator jest ślepy
> na zmianę zachowania przy niezmienionym opisie słownym. **Dokumenty „dobre" i „nieaktualne" napisałem
> ręcznie — żaden model nie był uruchamiany**, więc wynik mówi o walidatorze, nie o promptach.

## Struktura

```
code/
├── Retry/                  # kod, o którym piszemy dokumentację (Backoff, RetryExhaustedException), XML-doc OK
├── Retry.Stale/            # ten sam kod z celowo nieaktualnym XML-doc (ręcznie sfabrykowane rozjazdy)
├── Retry.Demo/             # konsola wykonująca przykłady z README/ADR (kod wyjścia != 0 przy rozjeździe)
├── docs-good/              # README.md + ADR-0001 zgodne z kodem (ręcznie)
├── docs-stale/             # README.md + ADR-0001 nieaktualne (ręcznie)
├── docs_check.py           # walidator: tryb `facts` (JSON do promptu) i `check`
├── drift_test.py           # 11 dryfów na kopii w /tmp, trzy detektory
└── prompts/                # xmldoc_/readme_/adr_ bad + good
```

## Jak uruchomić

Wymagania: .NET SDK (użyto 10.0.400), Python 3 (stdlib; użyto 3.10.4). Ścieżki względem katalogu
głównego repo; `-B` = bez `__pycache__`. Przykłady (README/ADR) mają ścieżki względem `code/`.

```bash
dotnet build days/2026-10-10/ai-prompts/code/Retry/Retry.csproj
dotnet build days/2026-10-10/ai-prompts/code/Retry.Stale/Retry.Stale.csproj
dotnet run --project days/2026-10-10/ai-prompts/code/Retry.Demo/Retry.Demo.csproj

python3 -B days/2026-10-10/ai-prompts/code/docs_check.py facts --root days/2026-10-10/ai-prompts/code --src Retry
python3 -B days/2026-10-10/ai-prompts/code/docs_check.py check --root days/2026-10-10/ai-prompts/code --src Retry --docs days/2026-10-10/ai-prompts/code/docs-good
python3 -B days/2026-10-10/ai-prompts/code/docs_check.py check --root days/2026-10-10/ai-prompts/code --src Retry.Stale --docs days/2026-10-10/ai-prompts/code/docs-stale

python3 -B days/2026-10-10/ai-prompts/code/drift_test.py              # kilka minut (12 buildów)
python3 -B days/2026-10-10/ai-prompts/code/drift_test.py --no-dotnet  # tylko walidator
```

`drift_test.py` pracuje na kopii w `/tmp` i sprząta po sobie; nie rusza plików w repo.
Kod wyjścia `check`: 0 = zgodne, 1 = rozjazdy.

## Weryfikacja — rzeczywisty output (uruchomione 2026-10-10, .NET 10.0.400)

### `dotnet build` — Retry (poprawne XML-doc) i Retry.Stale

```
Retry -> .../Retry/bin/Debug/net10.0/Retry.dll
Build succeeded.
    0 Warning(s)
    0 Error(s)
```

Retry.Stale (5 ostrzeżeń):

```
Backoff.cs(5,72): warning CS1574: XML comment has cref attribute 'BackoffOptions' that could not be resolved
Backoff.cs(21,22): warning CS1572: XML comment has a param tag for 'delay', but there is no parameter by that name
Backoff.cs(24,56): warning CS1573: Parameter 'baseDelay' has no matching param tag in the XML comment for 'Backoff.Delay(int, TimeSpan)' (but other parameters do)
Backoff.cs(50,22): warning CS1572: XML comment has a param tag for 'jitter', but there is no parameter by that name
Backoff.cs(57,50): warning CS1573: Parameter 'sleep' has no matching param tag in the XML comment for 'Backoff.RunAsync<T>(...)' (but other parameters do)
    5 Warning(s)
    0 Error(s)
```

(Skrócone: pominięto ścieżki do `.csproj` na końcu każdej linii.)

### `Retry.Demo` (exit 0)

```
OK   Delay(1, 100ms) == 100ms
OK   Delay(3, 100ms) == 400ms
OK   Delay(6, 10s) obciete do MaxDelay (30s)
OK   MaxAttempts == 6
OK   MaxDelay == 30s
OK   IsTransient(500)
OK   IsTransient(503)
OK   IsTransient(599)
OK   IsTransient(429)
OK   !IsTransient(404)
OK   !IsTransient(600)
OK   Delay(0, ...) -> ArgumentOutOfRangeException
OK   RunAsync: sukces w 3. probie, 2 oczekiwania (100ms, 200ms)
OK   RunAsync: po 6 probach RetryExhaustedException(Attempts=6), 5 oczekiwan
OK   RunAsync(null) -> ArgumentNullException
WSZYSTKO OK
```

### Walidator — dokumentacja zgodna (exit 0)

```
sprawdzono: 4 metod z XML-doc, 2 plikow .md
WYNIK: OK
```

### Walidator — dokumentacja nieaktualna (exit 1)

```
sprawdzono: 4 metod z XML-doc, 2 plikow .md
[XD01] Retry.Stale/Backoff.cs:24 Backoff.Delay: parametr `baseDelay` nie ma <param>
[XD02] Retry.Stale/Backoff.cs:24 Backoff.Delay: <param name="delay"> - w kodzie nie ma takiego parametru
[XD03] Retry.Stale/Backoff.cs:24 Backoff.Delay: kod rzuca ArgumentOutOfRangeException, brak <exception cref="ArgumentOutOfRangeException">
[XD04] Retry.Stale/Backoff.cs:24 Backoff.Delay: doc deklaruje ArgumentException, ale kod go nie rzuca
[XD01] Retry.Stale/Backoff.cs:54 Backoff.RunAsync: parametr `sleep` nie ma <param>
[XD02] Retry.Stale/Backoff.cs:54 Backoff.RunAsync: <param name="jitter"> - w kodzie nie ma takiego parametru
[XD03] Retry.Stale/Backoff.cs:54 Backoff.RunAsync: kod rzuca ArgumentNullException, brak <exception cref="ArgumentNullException">
[XD03] Retry.Stale/Backoff.cs:54 Backoff.RunAsync: kod rzuca RetryExhaustedException, brak <exception cref="RetryExhaustedException">
[XD04] Retry.Stale/Backoff.cs:54 Backoff.RunAsync: doc deklaruje TimeoutException, ale kod go nie rzuca
[XD08] Retry.Stale/Backoff.cs:6: `MaxAttempts` = 5, a w kodzie 6
[MD05] ADR-0001-exponential-backoff.md:13: `Backoff.MaxAttempts` = 5, a w kodzie 6
[AD02] ADR-0001-exponential-backoff.md: status 'Accepted' spoza ['Odrzucony', 'Proponowany', 'Przyjęty', 'Zastąpiony']
[AD03] ADR-0001-exponential-backoff.md: brak linii `Data: RRRR-MM-DD` z poprawna data
[AD04] ADR-0001-exponential-backoff.md: ADR nie wskazuje zadnego pliku `.cs`, ktorego dotyczy
[AD05] ADR-0001-exponential-backoff.md: Konsekwencje bez punktu `Negatywne:` (ADR bez kosztow to reklama)
[MD03] README.md:3: sciezka `Retry/Throttle.cs` nie istnieje
[MD01] README.md:3: `RetryPolicy` - brak takiego typu w kodzie (ani na liscie BCL_ALLOW)
[MD05] README.md:7: `Backoff.MaxAttempts` = 5, a w kodzie 6
[MD05] README.md:8: `Backoff.MaxDelay` = 60 s, a w kodzie 30000 ms
[MD02] README.md:15: `Backoff.ShouldRetry(httpStatus)` - typ Backoff nie ma skladowej `ShouldRetry`
[MD02] README.md:17: `RetryExhaustedException.AttemptCount` - typ RetryExhaustedException nie ma skladowej `AttemptCount`
[MD04] README.md:22: komenda wskazuje `Retry.Sample`, ktorego nie ma
WYNIK: ROZJAZDY: 22
```

### `drift_test.py` (exit 0)

```
id   walidator        kompilator         Retry.Demo opis
D00  OK               0 ostrzezen        OK         bez zmian (baseline)
D01  XD01             CS1573             OK         dodany parametr bez <param>
D02  XD03             0 ostrzezen        OK         kod rzuca nowy wyjatek, doc nie
D03  MD05,XD08        0 ostrzezen        FAIL x2    MaxAttempts 6 -> 8
D04  MD02             BLAD-KOMPILACJI    n/d        zmiana nazwy metody IsTransient
D05  MD01             0 ostrzezen        OK         zmiana nazwy typu wyjatku
D06  MD05             0 ostrzezen        FAIL x1    MaxDelay 30 s -> 60 s
D07  XD05             0 ostrzezen        OK         usuniete <returns>
D08  AD02             0 ostrzezen        OK         status ADR spoza slownika
D09  MD03             0 ostrzezen        OK         README wskazuje nieistniejacy plik
D10  OK               0 ostrzezen        FAIL x2    IsTransient: 500-599 -> 502-504 (tekst doc nie zmieniony)
D11  OK               0 ostrzezen        FAIL x3    Delay: 2^(attempt-1) -> 2^attempt (zachowanie)

walidator: 9/11  kompilator (nowe ostrzezenia lub blad): 2/11  Retry.Demo: 4/11
```

D04: „BLAD-KOMPILACJI" to błąd w projekcie `Retry.Demo` (wywołuje zmienioną nazwę), biblioteka `Retry` sama się
kompiluje — kolumna „kompilator" liczy więc D04 jako wykrycie.

## Co NIE jest zweryfikowane

- Że model z `*_good.txt` zastosuje się do promptów — **żaden model nie był uruchamiany**; `docs-good/`,
  `docs-stale/` i `Retry.Stale/` napisał człowiek (autor). „Nieaktualne" to sfabrykowane rozjazdy, nie zmierzony output.
- Reprezentatywność 11 dryfów (mój wybór, dobrany razem z regułami → zawyżone 9/11).
- Zachowanie walidatora na dużym repo; parser C# to regexy (brak atrybutów w sygnaturach, `throw` w metodach
  pomocniczych, `partial`, zagnieżdżone typy).
- Ślepe plamy walidatora: błąd treści słownej, argument dopisany w przykładzie wywołania (np. `jitter` w
  `docs-stale/README.md` nie został wykryty).
- Poprawność merytoryczna sekcji `Negatywne:` w ADR — walidator sprawdza tylko, że punkt istnieje.
- Pliki `prompts/*.txt` nie są lintowane (w odróżnieniu od #14); placeholdery `{{...}}` wypełnia człowiek/skrypt.
