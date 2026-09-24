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

## Rotacja tematów

Jedno wydanie = jeden temat z listy poniżej, w kolejności rotacyjnej (po ostatnim
wracamy do pierwszego). Dokładny wskaźnik "gdzie jesteśmy" trzyma `STATE.md` — zawsze
czytaj go przed napisaniem wydania i aktualizuj po.

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

- Jeden folder na dzień: `days/YYYY-MM-DD-krotki-slug-tematu/`
  - `ARTICLE.md` — treść wydania (nagłówek w stylu gazety, opis edukacyjny, ciekawostka).
  - `code/` — pełny, uruchamialny projekt + `code/README.md` (instrukcja uruchomienia +
    fragment artykułu).
- Każde wydanie dopisywane do tabeli w głównym `README.md` (spis treści gazety) z
  linkiem do `ARTICLE.md` i do `code/`.
- Stan rotacji/postępu per temat: `STATE.md`, aktualizowany po każdym wydaniu.
- Commit message: `Prasówka #<numer>: <tytuł wydania>`.
