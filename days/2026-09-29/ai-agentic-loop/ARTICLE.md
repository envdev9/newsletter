<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #6 — 29 września 2026

![AI/Agentic loop](https://img.shields.io/badge/AI_%2F_Agentic_loop-5A67D8?style=for-the-badge&logo=anthropic&logoColor=white)
![Poziom](https://img.shields.io/badge/poziom-zaawansowany-red?style=for-the-badge)
![Testy](https://img.shields.io/badge/asercje_lokalne-11%2F11-brightgreen?style=for-the-badge)
![Claude CLI](https://img.shields.io/badge/claude%20CLI-odrzucone%20przez%20uprawnienia-lightgrey?style=for-the-badge)

## Kto wybiera skill? Nie hook, nie Ty — model, po samym opisie

</div>

---

> _"Hook to jest `if`, który harness wykonuje za Ciebie, zanim zdążysz zapytać. Skill to
> jest akapit, który model musi sam sobie zechcieć przeczytać — a decyduje o tym jedno pole
> w nagłówku pliku."_

Do tej pory w tej rubryce: pętla tool-use i różnica komenda/skill/subagent/hook (#1), hooki
i pierwszy własny skill `changelog-entry` (#2), własny subagent `dotnet-reviewer` i pętla
z weryfikacją (#3), wachlarz subagentów i bramka CI (#4). Wszystkie te mechanizmy mają jedną
wspólną cechę: **kto naciska spust jest z góry określony przez harness** — hook odpala się
zawsze na dany event, subagent ma z góry zawężone `tools`. Dziś mechanizm jest inny:
**skille nie mają wyzwalacza zewnętrznego**. Model w trakcie pracy sam czyta listę
zainstalowanych skilli (nazwa + `description`) i sam ocenia, czy któryś jest relewantny do
tego, co właśnie robi — bez reguły, bez `if`, bez hooka, który by to wymuszał. Kod: [`code/`](code/).

> ⚠️ **Uczciwie na starcie:** w tym środowisku każda komenda zawierająca `claude` (w tym
> `claude --version`, `which claude`) jest **odrzucana przez uprawnienia** — dokładnie jak
> w wydaniach #3 i #4 tej rubryki. Nie obejmowałem tego. **Żaden** fragment poniżej dotyczący
> prawdziwego CLI/sesji nie był uruchomiony. Wszystko, co dało się sprawdzić lokalnie
> (parsowanie frontmattera, mechanizm decyzji "czy opis pasuje do zadania", granice takiej
> symulacji), sprawdziłem realnie — Python 3.10, bez zależności, `python3 code/run_tests.py`
> daje **11/11**. Nazwy pól/mechanizmów z pamięci są jawnie oznaczone jako niezweryfikowane.

---

## 1️⃣ 🧭 Mechanizm: to NIE jest routing po słowach kluczowych

### 🎯 Dlaczego to jest inny temat niż hooki i `tools` subagenta

W #2 hook `UserPromptSubmit` odpala się na **każdy** prompt — harness go wykonuje
deterministycznie, niezależnie od treści. W #3 subagent `dotnet-reviewer` ma `tools: Read,
Grep, Glob` zapisane w pliku — to jest twarda reguła wymuszana przez harness, nie decyzja
modelu w danej chwili. Skill działa inaczej: **nikt nie wywołuje skilla za model**. Z pamięci
(nie zweryfikowane w tej sesji — brak żywego CLI): Claude Code na starcie sesji ma w
kontekście krótką listę zainstalowanych skilli — tylko `name` i `description` z frontmattera,
**nie** całą treść `SKILL.md`. To jest kluczowe dla kosztu: dziesięć skilli po kilkaset linii
instrukcji nie zajmuje miejsca w kontekście, dopóki żaden nie zostanie użyty — ładuje się
(czyta pełną treść pliku) **tylko ten, który model sam uzna za potrzebny w danym momencie**,
i tylko wtedy. To bywa nazywane "progressive disclosure" — ale sedno tego wydania nie jest
w mechanice ładowania samej treści (to już częściowo omawialiśmy przy komendach/skillach w #1),
a w tym, **na jakiej podstawie model podejmuje tę decyzję**: czyta `description` i ocenia
semantycznie, czy opisana sytuacja pasuje do tego, co robi teraz. To jest ocena modelu, nie
dopasowanie wzorca przez harness.

### Dlaczego to różni się od "keyword matching"

Człowiek pisze zadanie swoimi słowami — czasem dosłownie tak, jak brzmi opis skilla
("dotnet test failuje"), a czasem parafrazą ("coś się psuje w pipeline, mimo że nikt nic nie
zmieniał"). Deterministyczny router po słowach kluczowych złapie pierwsze zdanie i przegapi
drugie, mimo że to **ten sam problem**. Prawdziwy model, czytając `description`, rozumie że
"psuje się w pipeline" i "dotnet test failuje" mogą być tym samym zjawiskiem — o ile
`description` w ogóle dało mu wystarczający kontekst, żeby to skojarzyć. To przenosi ciężar
z mechanizmu (harness) na **treść opisu** — i to jest haczyk tego wydania: **dobre
`description` to inżynieria promptu, nie metadane**. Piszesz je nie dla człowieka
przeglądającego listę plików, a dla modelu, który w ułamku sekundy decyduje "pasuje / nie
pasuje", mając do dyspozycji tylko te 1-3 linijki, zanim zdąży przeczytać cokolwiek więcej.

---

## 2️⃣ ✍️ Dobry i zły `description` — na żywych przykładach

W [`code/skills/`](code/skills/) leżą cztery skille (plus jedna dodatkowa wersja) — każdy
tylko z frontmatterem różniącym `description`, treść proceduralna identyczna, gdzie to
możliwe, żeby izolować **jedną** zmienną:

| Skill | Kategoria | `description` (skrót) |
|---|---|---|
| [`ef-core-migration-safety`](code/skills/ef-core-migration-safety/SKILL.md) | ✅ dobry, konkretny | wymienia dokładne operacje (`DROP COLUMN`, zmiana typu, `NOT NULL` bez defaultu, brak indeksu na FK) + kiedy użyć (`dotnet ef migrations add`, pytanie "czy migracja jest bezpieczna na produkcji") |
| [`dotnet-test-triage-v1-narrow`](code/skills/dotnet-test-triage-v1-narrow/SKILL.md) | ⚠️ dobry temat, zbyt wąski opis | tylko literalne "dotnet test", "czerwone testy" — żadnej parafrazy |
| [`dotnet-test-triage-v2-broad`](code/skills/dotnet-test-triage-v2-broad/SKILL.md) | ✅ dobry, zaprojektowany pod parafrazy | ta sama procedura co v1, opis dodaje "pipeline się wywalił", "działało wczoraj a dziś nie", "nikt nic nie zmieniał" — jawnie zapisane warianty zgłoszenia tego samego problemu |
| [`dotnet-helper`](code/skills/dotnet-helper/SKILL.md) | ❌ zły, ogólny | "Pomaga z zadaniami związanymi z .NET" — pasuje do wszystkiego i do niczego |
| [`general-code-assistant`](code/skills/general-code-assistant/SKILL.md) | ❌ zły, ogólny | "Ogólny asystent do kodu i programowania" — te słowa padają w prawie każdym zadaniu deweloperskim |

Para v1/v2 to najważniejsza rzecz w tym zestawie: **identyczna treść, identyczne
`allowed-tools`, różni się tylko `description`.** To dowodzi, że o tym, czy skill w ogóle
dostanie szansę zadziałać, decyduje **wyłącznie** to jedno pole — nie jakość instrukcji
w środku. Możesz napisać najlepszą procedurę triażu testów w firmie i model nigdy jej nie
użyje, jeśli opis nie przewiduje, jak ludzie faktycznie zgłaszają problem.

> 💡 **Zasada z tego zestawu:** dobry opis odpowiada na trzy pytania w 1-3 zdaniach —
> *co robi skill* (konkretne operacje/objawy, nie "pomaga z X"), *kiedy go użyć* (kilka
> wariantów zgłoszenia, nie jedna fraza), *czym się różni od podobnych skilli* (żeby model
> nie musiał zgadywać między dwoma kandydatami o podobnym temacie). Zły opis łamie
> wszystkie trzy naraz — i to działa w obie strony: zbyt ogólny opis albo nigdy się nie
> odpali (model nie wie, że to "to", bo "to" nie jest niczym konkretnym), albo odpali się
> zawsze (bo teoretycznie "pomaga z kodem" pasuje do każdego zadania) — żadne z tych dwóch
> nie jest tym, czego chcesz.

---

## 3️⃣ 🧪 Symulacja mechanizmu decyzji — i jej granice

### Co i jak symuluję

[`code/skill_router_sim.py`](code/skill_router_sim.py) **nie jest modelem językowym**. To
prosta heurystyka: tokenizuje `description` każdego skilla i tekst zadania (bez odmiany,
bez synonimów), waży każde słowo odwrotnością liczby skilli, w których się pojawia (żeby
"dotnet"/"core", obecne w kilku opisach naraz, nie decydowały tak samo jak "pipeline",
które identyfikuje jeden konkretny skill), i liczy ważony recall słów zadania w opisie.
Wynik ≥ próg (`0.12`) → `LOAD`, inaczej `skip`. To pokazuje **sam mechanizm** (przeczytaj
opis → oceń trafność → załaduj albo nie) i typowe pułapki opisu, ale — trzeba to
powiedzieć wprost — **nie mierzy tego, jak model faktycznie ocenia trafność**. Model rozumie
znaczenie i kontekst; ten skrypt liczy wyłącznie powtórzenia liter.

### Pięć scenariuszy, prawdziwy output

Uruchomienie `python3 code/run_tests.py` (Python 3.10, bez zależności) daje ten output —
skrócone tabele dla każdego scenariusza (pełny output, z komentarzami, jest w
[`code/README.md`](code/README.md)):

```
### A-literal-match
zadanie: "Test dotnet test failuje po tym jak zmienilem model domeny i dodalem migracje EF Core..."
ef-core-migration-safety          0.427     LOAD  core, domeny, dotnet, ef, kolumny, migracje, model
dotnet-test-triage-v2-broad       0.124     LOAD  dotnet, failuje, test
dotnet-test-triage-v1-narrow      0.056     skip  dotnet, test
dotnet-helper                       0.0     skip  -
general-code-assistant              0.0     skip  -

### B-paraphrase
zadanie: "Cos sie psuje w pipeline dokladnie tam gdzie sprawdzamy poprawnosc kodu, mimo ze nikt nic nie zmienial od wczoraj."
dotnet-test-triage-v2-broad       0.333     LOAD  pipeline, wczoraj, zmienial
general-code-assistant            0.111     skip  kodu
dotnet-test-triage-v1-narrow        0.0     skip  -

### C-migration-clear
zadanie: "Migracja dodaje DROP COLUMN na tabeli Orders, kolumna Legacy - czy taka migracja jest bezpieczna do wgrania na produkcji?"
ef-core-migration-safety          0.583     LOAD  bezpieczna, column, dodaje, drop, migracja, produkcji, wgrania

### D-unrelated
zadanie: "Jak skonfigurowac Serilog zeby wysylal logi do Seq z poziomu ASP.NET Core?"
ef-core-migration-safety          0.105     skip  core
dotnet-helper                     0.053     skip  net
(zaden skill nie przekracza progu)

### E-inflection-limit
zadanie: "Chcemy dropnac kolumne Legacy z tabeli Orders w nowej migracji, czy to bezpieczne na produkcji?"
ef-core-migration-safety            0.1     skip  produkcji
(sygnal jest, ale za slaby - patrz sekcja o ograniczeniach)

WYNIK: 11/11
```

### Co te pięć scenariuszy uczy

| # | Co pokazuje | Wniosek |
|---|---|---|
| **A** | Zadanie dotyka dwóch tematów naraz, używa słów wprost z opisów | Oba trafne skille się "zapalają" (`LOAD`); `v1-narrow` mimo trafnego tematu **ledwo nie łapie progu** — krótszy, mniej rozbudowany opis daje słabszy sygnał nawet dla własnej, dosłownej frazy |
| **B** | Ten sam problem jak w A, opisany parafrazą, bez słowa "test"/"dotnet" | Tylko `v2-broad` (opis zaprojektowany pod warianty zgłoszenia) łapie. `v1-narrow` = **0.0** — całkowity miss. To jest realny koszt złego opisu, nie kosmetyka |
| **C** | Jednoznaczna domena, słowa dopasowane do opisu | Jeden skill wygrywa wyraźnie (0.583, próg 0.12) — tak powinien wyglądać "łatwy" przypadek |
| **D** | Zadanie niezwiązane z żadnym skillem | Nic nie przekracza progu — **domyślny stan to brak decyzji, nie "zgadnij najbliższe"**. To jest właściwość, którą chcesz mieć w prawdziwym systemie: brak trafienia ≠ załaduj coś na siłę |
| **E** | Ten sam temat co C, inna odmiana słów (`kolumne`/`kolumny`, `migracji`/`migracje`) | Sygnał jest (0.1), ale **poniżej progu** — czysta heurystyka bag-of-words bez stemmingu gubi nawet trafny skill przez polską odmianę. To ograniczenie symulacji, nie mechanizmu Claude Code — model rozumie, że "dropnąć kolumnę" i "DROP COLUMN" to to samo, ten skrypt nie |

Scenariusz **B** jest najbliżej prawdziwej pułapki opisu-worka: `general-code-assistant`
("ogólny asystent do kodu i programowania") dostaje niezerowy wynik (0.111) tylko dlatego, że
zadanie zawiera słowo "kodu" — ale dzięki wadze `1/liczba_skilli_ze_slowem` (to słowo
pojawia się tylko w tym jednym opisie, więc nie jest dodatkowo tłumione) i tak **nie**
przekracza progu, bo resztę zadania nie łączy z niczym innym. W wersji **bez** tego
ważenia (zwykły, nieważony recall) ten sam wynik 0.111 przy niżej ustawionym progu (0.10,
sprawdzone ręcznie w tej sesji przed dodaniem wagi) **realnie przekracza próg i wygrywa
false-positive** nad skillem `v1-narrow`, który dla tego zadania daje 0.0. Innymi słowy:
**nawet ta uboga heurystyka pokazuje mechanizm, przez który zbyt ogólny opis wygrywa nad
zbyt wąskim, poprawnym** — a to jest właśnie ryzyko, przed którym ostrzega ten artykuł,
tylko przesunięte z "modelu, który się myli" na "skrypt, który się myli w ten sam sposób,
z tego samego powodu: brak sygnału odróżniającego".

> ⚠️ **Czego symulacja NIE dowodzi:** że prawdziwy model popełni identyczne błędy. Model
> semantyczny prawdopodobnie złapie parafrazę z B nawet dla `v1-narrow` (rozumie, że "coś się
> psuje po tym jak nic nie zmieniano" to opis regresji/flaky testu) i poprawnie zignoruje
> `general-code-assistant` (rozumie, że "sprawdzamy poprawność kodu" w kontekście awarii
> pipeline'u nie jest tym samym co ogólna prośba o pomoc z kodem). Nie sprawdziłem tego na
> żywej sesji — CLI odrzucone. Ta symulacja dowodzi tylko **istnienia punktu decyzyjnego**
> (opis → ocena trafności → load/skip) i **konsekwencji złego opisu**, nawet gdy ocena
> trafności jest głupia. Gdy ocena trafności jest mądra (prawdziwy model), złe opisy nadal
> szkodzą — tylko w innych, bardziej subtelnych miejscach (dwa podobne skille, oba
> pasujące, model wybiera intuicyjnie który pierwszy — tego nie zbadałem).

> 💡 **Analogia .NET (częściowa — nie ma tu dobrego 1:1):** to bliżej wyszukiwania
> pełnotekstowego (ocena trafności dokumentu do zapytania) niż DI kontenera czy
> `[Route]`-matching w ASP.NET Core, które są deterministyczne i jednoznaczne. Różnica: DI
> rozstrzyga po **typie**, routing po **wzorcu URL** — oba dają ten sam wynik dla tego
> samego wejścia, zawsze. Wybór skilla po `description` nie daje takiej gwarancji, bo
> "trafność" ocenia model, nie parser. To jest cena za to, że w ogóle można złapać parafrazę.

---

## 📎 Co zweryfikowano, a czego nie

| ✅ Uruchomione naprawdę (Python 3.10, bez zależności) | ⚠️ Niezweryfikowane |
|---|---|
| `python3 code/run_tests.py` — **11/11** asercji na 5 scenariuszach (A-E), w tym scenariusz D (nic nie przekracza progu) i E (limit heurystyki na odmianie) | Że Claude Code faktycznie ładuje tylko `name`+`description` na starcie, a pełną treść dopiero po wyborze — z pamięci, nie z dokumentacji w tej sesji |
| Parsowanie frontmattera 5 plików `SKILL.md`, wagi `1/df` liczone realnie z korpusu opisów | Jak model semantycznie ocenia `description` — symulacja liczy tylko powtórzenia słów, nie znaczenie |
| Ręczne porównanie: nieważony recall przy niższym progu daje false-positive `general-code-assistant` nad `v1-narrow` w scenariuszu B (sprawdzone przed dodaniem wagi `1/df`) | Zachowanie przy kilku pasujących skillach naraz (który wygrywa, czy oba się ładują) w żywej sesji |
| `claude` w PATH: **nie sprawdzone** — każda komenda z `claude` odrzucona przez uprawnienia (jak w #3, #4) | `claude --help`, realny format frontmattera skilla, pole `allowed-tools` a nazwa/semantyka w Twojej wersji |

Nie miałem dostępu do dokumentacji online w tej sesji — twierdzenia o mechanizmie ładowania
skilli oznaczone "z pamięci" sprawdź w dokumentacji swojej wersji Claude Code, zanim
zaprojektujesz na tym system opisów dla większego zestawu skilli.

---

<div align="center">

[← wróć do wydania #6 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
