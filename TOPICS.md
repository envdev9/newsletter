# Konfiguracja prasówki

Ten plik czyta agent generujący codzienne wydanie. Redaguj go dowolnie — kolejne
przebiegi zawsze biorą najnowszą wersję.

## Misja

Codzienne wydanie ma dawać czytelnikowi **namacalne poczucie postępu** — każdego dnia
jedna konkretna, nowa rzecz do zrozumienia, nie ogólnik. Priorytety przy pisaniu:

1. **Zero nudy.** Nie przepisujemy dokumentacji. Każdy wpis ma hak — "dlaczego to
   ważne", "jaki problem to rozwiązuje", "czym to się różni od tego co było wcześniej".
2. **Zero fikcji.** Jeśli agent nie jest pewien faktu/wersji/zachowania — pomija go albo
   wyraźnie zaznacza niepewność. Nie zmyślamy nazw API ani wyników działania kodu.
3. **Zawsze coś działającego.** Każdy wpis techniczny ma pełny, uruchamialny kod w repo
   (nie fragmenty wyrwane z kontekstu) + dokładne komendy CLI do odpalenia go od zera.
   Kod musi się skompilować/uruchomić zanim wpis trafi do commita.
4. **Poziom czytelnika: zaawansowany .NET dev, zero wiedzy w danej pobocznej dziedzinie.**
   Ansible/TeamCity/TUnit/Aspire/MassTransit/AI — zakładamy, że czytelnik nie zna tematu,
   więc zaczynamy od podstaw i stopniowo podnosimy poziom trudności w kolejnych wydaniach
   tego samego tematu (nie każde wydanie od zera — patrz `STATE.md`, kontynuujemy tam gdzie
   skończyliśmy).

## Wygląd

Prasówka ma wyglądać jak gazeta, nie jak sucha dokumentacja — kolorowo, z nagłówkiem
("mastheadem"), o ile pozwala na to Markdown renderowany przez GitHub (bez `<style>`,
za to śmiało: tabele, `shields.io` badge'e, emoji jako "ikony" rubryk, `<details>` do
zwijania starszych sekcji, cytaty blokowe na "cytat/ciekawostkę dnia", separator `---`
między sekcjami). Każda dziedzina ma stały emoji/kolor badge'a, żeby całość była łatwa
do skanowania wzrokiem jak dział w gazecie. Szczegóły layoutu głównego `README.md` — nie
psuj konwencji, którą tam ustaliliśmy, rozszerzaj ją.

## Rubryki — codziennie WSZYSTKIE, nie rotacyjnie

**Jedno wydanie (jeden dzień) = jeden artykuł z KAŻDEJ rubryki poniżej.** To nie jest
rotacja "dziś temat A, jutro temat B" — każdego dnia czytelnik dostaje postęp we
wszystkich dziedzinach naraz, jak dział w prawdziwej gazecie (sport, polityka,
technologia... tu: .NET, Ansible, TeamCity, ...). Każda rubryka ma **własny, niezależny
postęp** (wersja .NET, poziom trudności Ansible/TeamCity/itd.) trzymany w `STATE.md` —
ten postęp przesuwa się o jeden krok dziennie, per rubryka, niezależnie od pozostałych.
Zawsze czytaj `STATE.md` przed pisaniem wydania i aktualizuj po (osobna sekcja per
rubryka). Lista rubryk może z czasem rosnąć (dopisywana ręcznie) — trzymaj się aktualnej
listy poniżej, nie tej zapamiętanej z poprzednich przebiegów.

1. **.NET — nowości w wersji** 🔷: opisz 2 nowe funkcje danej wersji .NET, z pełnym,
   kompilującym się przykładem kodu na każdą + wyjaśnieniem "co to zmienia w praktyce".
   Zaczynamy od **.NET 10**, potem **.NET 11**, i tak w górę — gdy nowości w najnowszej
   wersji się wyczerpią (agent sam ocenia, kiedy dana wersja jest "przegadana"), **schodzimy
   w dół**: 9, 8, 7, aż do **.NET 6** (LTS-y i ważne funkcje, nie trzeba każdej wersji
   traktować tak samo obszernie).
2. **Ansible** 🔧: jak się pisze playbooki — składnia, zmienne, inwentarz, wywołania,
   handlery, role. Zaczynamy od zupełnych podstaw (czytelnik nic nie wie), każde kolejne
   wydanie o tym temacie podnosi poziom o jeden stopień. Przykład zawsze uruchamialny
   (`ansible-playbook ...`), na początek prościutki (np. `localhost`/`ansible_connection:
   local`, bez potrzeby prawdziwej floty serwerów).
3. **TeamCity** 🏗️: jak wyżej — od podstaw (build configuration, VCS root, build step,
   trigger) w górę do bardziej zaawansowanych (templates, dependencies, Kotlin DSL).
4. **TUnit** 🧪: nowoczesny framework testowy dla .NET — od podstaw (pierwszy test,
   asercje, source-generated testy) w górę (data-driven testy, hooki, równoległość).
5. **Aspire** ✈️: orkiestracja lokalnego środowiska .NET — od podstaw (AppHost, pierwszy
   zasób) w górę (service discovery, integracje, telemetry).
6. **Messaging .NET z MassTransit** 📨: od podstaw (consumer, producer, in-memory
   transport) w górę (sagas, routing, retry/error handling, RabbitMQ).
7. **AI — Claude Code dla .NET/Angular/SQL** 🤖: konkretne, gotowe do skopiowania
   przypadki użycia usprawniające codzienną pracę dewelopera w tym stacku — co dokładnie
   się robi i co się przez to zyskuje (nie ogólniki o "AI pomaga kodować").
8. **AI — agentic loop / workflow kodowania** ⚙️: jak budować pętlę agentową do pracy nad
   kodem — konkretne przykłady: agenci, skille, komendy, hooki. Obszerne, dogłębne
   wyjaśnienia mechanizmu, nie tylko "co kliknąć".
9. **AI — zarządzanie kontekstem** 🧠: jak analizować co i w jakiej kolejności trafia do
   kontekstu, jakimi narzędziami to sprawdzać, jak efektywnie dzielić zadania i co dawać
   modelowi do ręki a co nie. Cel: czytelnik ma wyjść na poziomie mistrzowskim w zarządzaniu
   kontekstem, nie na poziomie ciekawostki.
10. **AI — prompty dla developera** ✍️: co i jak pisać w promptach, jak formułować zadania,
    czego unikać, konkretne przykłady złego i dobrego promptu z komentarzem dlaczego.
11. **Angular** 🅰️: nowoczesny Angular — signals, `ngrx/signals` (signal store), nowe
    funkcje od wersji 19 wzwyż. Nie trzeba iść wersja po wersji chronologicznie — sam
    dobierz kolejność, która najlepiej buduje zrozumienie (np. najpierw signals jako
    fundament, potem signal store, potem nowości frameworka na tym bazujące). Plus RxJS —
    ale tylko operatory, które są realnie sensowne w praktyce (nie cały katalog RxJS).
12. **SQL Server** 🗄️: od podstaw (SELECT, JOIN, podstawowe typy) do przykładów
    zaawansowanych (indeksy, plany wykonania, optymalizacja zapytań). Przykłady z
    plikami wsadowymi (`.sql` uruchamiane przez `sqlcmd`), tak żeby czytelnik mógł sam
    odpalić i zobaczyć np. różnicę w planie wykonania z indeksem i bez.
13. **PostgreSQL jako baza wektorowa** 🧬: `pgvector`, przykłady z embeddingami — jak
    wygląda kolumna wektorowa, jak się indeksuje (IVFFlat/HNSW), jak wygląda realne
    wyszukiwanie podobieństwa. Model embedujący dobierz tak, żeby przykład dało się
    odpalić bez płatnych kluczy API (lokalny model / deterministyczny przykład
    ilustrujący mechanikę indeksu, jeśli lokalny model embeddingowy jest zbyt ciężki).
14. **Certyfikaty i TLS (X.509)** 🔐: wszystko co developer powinien wiedzieć o
    certyfikatach — nie tylko w .NET, ale ogólnie. Teoria od podstaw (klucz
    publiczny/prywatny, łańcuch zaufania, CA, self-signed vs CA-signed, czym różni się
    TLS 1.2 od 1.3) i praktyka (.NET: `X509Certificate2`, walidacja certyfikatu, mTLS,
    konfiguracja Kestrel/HTTPS, magazyn certyfikatów; poza .NET: `openssl`, generowanie i
    inspekcja certyfikatów, typowe błędy zaufania i jak je diagnozować). **To ma
    przyświecać całej tej rubryce: cel to poziom MISTRZOWSKI** — czytelnik ma po serii
    wydań rozumieć certyfikaty na wylot, nie znać kilku ciekawostek. Poziom trudności
    rośnie z każdym kolejnym wydaniem tego tematu, jak w pozostałych rubrykach.

## Wymagania co do kodu

- Kod ma się **realnie kompilować/uruchamiać** — agent musi to zweryfikować lokalnie
  (`dotnet build`/`run`, `ansible-playbook --syntax-check` + faktyczne odpalenie,
  odpowiedni odpowiednik dla innych technologii) **przed** commitem, nie zakładać że
  zadziała.
- Pełny, samodzielny projekt w repo (nie snippet) + dokładne komendy CLI "jak to odpalić
  od zera" w `code/README.md` danego wydania.
- `code/README.md` danego wydania zawiera też skopiowany fragment artykułu, którego kod
  dotyczy — kod i opis nie mogą żyć rozłącznie.

## Gdzie i jak zapisywać

- Jeden folder na dzień (wydanie): `days/YYYY-MM-DD/`
  - `README.md` — **strona tytułowa wydania**: krótkie zajawki wszystkich 10 rubryk tego
    dnia z linkami do artykułów (wzór: dowolny istniejący `days/*/README.md`).
  - Jeden podfolder na rubrykę, stały slug: `dotnet/`, `ansible/`, `teamcity/`, `tunit/`,
    `aspire/`, `masstransit/`, `ai-claude-code/`, `ai-agentic-loop/`, `ai-context/`,
    `ai-prompts/`. W każdym:
    - `ARTICLE.md` — treść (nagłówek w stylu gazety, opis edukacyjny).
    - `code/` — pełny, uruchamialny projekt/skrypt + `code/README.md` (instrukcja
      uruchomienia + fragment artykułu, którego dotyczy).
- Główny `README.md` (spis treści całej gazety): **jeden wiersz na dzień** (nie na
  rubrykę) w tabeli "Spis wydań", link do `days/YYYY-MM-DD/README.md`. Sekcja "Dziś na
  pierwszej stronie" pokazuje zajawkę najnowszego dnia.
- Postęp per rubryka: `STATE.md`, osobna sekcja na rubrykę, aktualizowana po każdym
  wydaniu (każda rubryka co dzień, więc każda sekcja rusza się co dzień).
- Commit message: `Prasówka #<numer>: <data>` (jeden commit na cały dzień, wszystkie 10
  rubryk razem).
