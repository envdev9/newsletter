ZADANIE
Napisz docs-good/README.md dla biblioteki w katalogu Retry/. Czytelnik: programista .NET,
który chce zdecydować, czy użyć biblioteki, i uruchomić przykład.

DANE (jedyne źródło faktów)
<facts>{{wynik: python3 -B docs_check.py facts --root . --src Retry}}</facts>
<source file="Retry/Backoff.cs">{{treść}}</source>
<source file="Retry/RetryExhaustedException.cs">{{treść}}</source>
<project name="Retry.Demo" run="dotnet run --project Retry.Demo">przykłady wykonywane na kodzie</project>

STRUKTURA (dokładnie te sekcje, w tej kolejności)
1. Jednozdaniowy opis: co robi i czego NIE robi.
2. Stałe - lista w formie: `Typ.Nazwa` = wartość [jednostka]. Jednostka (s/ms) wymagana dla czasu.
3. API - tabela: składowa | co robi | wyjątki. Każda publiczna metoda z facts, nic spoza facts.
4. Przykład - tylko takie, które wykonuje Retry.Demo; nie wymyślaj nowych wartości wyjściowych.
5. Uruchomienie - polecenia dokładnie z <project>.

ZASADY
- Nazwy typów i składowych w `backtickach`, dokładnie jak w facts. Ścieżki do plików tylko istniejące.
- Nie opisuj funkcji, których nie ma w facts (jitter, konfiguracja z pliku, integracja z Polly) -
  nawet jeśli biblioteki tego typu zwykle je mają.
- Żadnych przymiotników marketingowych ("potężny", "elastyczny", "enterprise-ready").
- Jeśli brakuje Ci informacji, zapisz ją w sekcji "Do uzupełnienia przez autora" na końcu.

GOTOWE, GDY
`python3 -B docs_check.py check --root . --src Retry --docs docs-good` zwraca 0.
