<div align="center">

# 📰 TECH PRASÓWKA
### Wydanie #17 — 10 października 2026

![AI](https://img.shields.io/badge/AI_%2F_Prompty-D97757?style=for-the-badge&logo=anthropic&logoColor=white)
![.NET](https://img.shields.io/badge/.NET_10-512BD4?style=for-the-badge&logo=dotnet&logoColor=white)
![Python](https://img.shields.io/badge/walidator-Python_stdlib-3776AB?style=for-the-badge&logo=python&logoColor=white)

## Dokumentacja, która kłamie po tygodniu: prompty do XML-doc, README i ADR z walidatorem zgodności z kodem

</div>

---

> _"Model napisze dokumentację, która brzmi jak dokumentacja. Czy opisuje TEN kod, a nie
> kod, który widział tysiąc razy - to się da sprawdzić skryptem."_

Poprzednio w tej rubryce: [#14 - testy i mutanty](../../2026-10-07/ai-prompts/ARTICLE.md)
(tam padło: „testy mierz mutacjami"; dziś o testach nie piszę). Dziś **dokumentacja**:
komentarze XML-doc, README i ADR. Zapowiedź z #14 - „dokumentacja jeszcze nie omówiona".

**🎯 Dlaczego to ważne:** dokumentacja z modelu ma dwa tryby awarii. Pierwszy: **zmyśla** (parametr,
którego nie ma, wyjątek, którego metoda nie rzuca, „wsparcie dla jittera" w bibliotece bez jittera).
Drugi: **starzeje się po cichu** - kod zmienia się za miesiąc, dokument zostaje. Oba mają to samo
lekarstwo: fakty o kodzie wchodzą do promptu **ze skryptu**, a wynik wraca przez ten sam skrypt jako
walidator. Prompt mówi modelowi *co ma napisać*, walidator sprawdza *czy się zgadza*.

> ⚠️ **Uczciwie na starcie: żaden model nie był uruchamiany.** Dokumenty „dobre" (`docs-good/`) i „nieaktualne"
> (`docs-stale/`, `Retry.Stale/`) napisałem **ja, ręcznie**. „Nieaktualne" to nie zmierzony output modelu bez faktów -
> to *fabrykacja typowych rozjazdów*, żeby było co wykrywać. Mierzę **walidator**, nie prompty.

---

### 1️⃣ Kod, o którym piszemy dokumentację

[`code/Retry/Backoff.cs`](code/Retry/Backoff.cs) (.NET 10, zero pakietów): wykładniczy backoff.
`Delay(attempt, baseDelay)`, `IsTransient(httpStatus)`, `RunAsync(...)`, stałe `MaxAttempts = 6`,
`MaxDelay = 30 s`, wyjątek `RetryExhaustedException`. Mały, ale z cechą, która dokumentację psuje
najczęściej: ma **stałe liczbowe, wyjątki i parametry, które łatwo rozjechać z tekstem**.

---

### 2️⃣ Trzy pary zły / dobry prompt

Pełne teksty w [`code/prompts/`](code/prompts/). Cała trójka ma wspólny wzorzec:

| | ❌ Zły | ✅ Dobry | Dlaczego |
|---|---|---|---|
| **XML-doc** | _„Dodaj dokumentację XML do klasy Backoff."_ | Facts ze skryptu (`params`, `throws`, `constants`) jako źródło prawdy + zmieniaj tylko `///` + `<c>Nazwa = wartość</c>` + „czegoś nie wiesz → `BRAK DANYCH`" | Model „widzi" kod, ale zgaduje wyjątki (najczęściej dopisuje `ArgumentNullException` wszędzie) i parafrazuje nazwy: „Delay: oblicza opóźnienie". Lista `throws` z ciała metody eliminuje zgadywanie. |
| **README** | _„Napisz README... profesjonalne i opisuje wszystkie funkcje."_ | Dokładna struktura sekcji + „opisuj tylko to, co jest w facts" + zakaz funkcji „które takie biblioteki zwykle mają" + przykłady tylko te, które wykonuje `Retry.Demo` | „Wszystkie funkcje" to zaproszenie do dopisania typowych: jitter, konfiguracja, integracja z Polly. Zakaz z nazwami konkretnych urojeń działa lepiej niż „nie zmyślaj". |
| **ADR** | _„Napisz ADR o tym, że używamy backoffu wykładniczego."_ | Decyzja i kontekst **od człowieka**, format sekcji i słownik statusów, `Negatywne:` obowiązkowe, zakaz „powodów spoza kontekstu" | ADR to zapis *dlaczego*. Model nie zna waszych powodów, więc je wymyśli („ze względu na wydajność"). Bez wymuszonych negatywnych konsekwencji ADR zamienia się w reklamę decyzji. |

Trzy elementy, które odróżniają dobry prompt dokumentacyjny od „napisz opis":

1. **Podział źródeł: kod = *co*, człowiek = *dlaczego*, skrypt = *liczby i nazwy*.** Model nie ma skąd wziąć
   motywacji decyzji; dajesz mu ją albo każesz zostawić `BRAK DANYCH`.
2. **Kontrakt wyjścia sprawdzalny maszynowo.** `Nazwa = wartość`, `## Status` z jednego słowa ze słownika,
   `Negatywne:` - format jest wąski nie dla estetyki, tylko żeby walidator mógł go zjeść.
3. **„Gotowe, gdy" = komenda.** Nie „sprawdź czy się zgadza", tylko `docs_check.py check ...` z kodem wyjścia.

Ten sam schemat to **łańcuch z kontraktem między krokami**: (1) skrypt `facts` → JSON, (2) model
→ plik z dokumentacją, (3) skrypt `check` → kod wyjścia. Kontraktem kroku 1→2 jest JSON z faktami,
kroku 2→3 - format dokumentu. Krok 2 jest jedynym nieuruchomionym w tym artykule.

---

### 3️⃣ Walidator: co sprawdza

[`code/docs_check.py`](code/docs_check.py) (Python stdlib). **To nie jest Roslyn** - to regexy dobrane pod
styl tego kodu (jedna deklaracja = jedna sygnatura, bez atrybutów w liście parametrów).

| Reguła | Sprawdza |
|---|---|
| XD01/XD02 | parametr bez `<param>` / `<param>` bez parametru |
| XD03/XD04 | wyjątek rzucany w ciele (`throw new X`, `ThrowIfNull`...) bez `<exception>` / `<exception>` bez rzucającego kodu |
| XD05/XD06/XD07 | `<returns>` zgodny z typem zwracanym, `<typeparam>`, poprawność XML |
| XD08, MD05 | liczba przy nazwie stałej w dokumencie = wartość w kodzie (jednostki s/ms) |
| MD01/MD02 | `` `Typ` `` / `` `Typ.Składowa` `` w README i ADR istnieje w kodzie |
| MD03/MD04 | ścieżka w backtickach istnieje; `dotnet run/build ...` wskazuje istniejący projekt |
| AD01-AD05 | ADR: sekcje, status ze słownika, data, plik `.cs`, punkt `Negatywne:` |

Na kodzie z poprawną dokumentacją (`docs-good/`):

```
sprawdzono: 4 metod z XML-doc, 2 plikow .md
WYNIK: OK
```

Na „nieaktualnej" dokumentacji (`Retry.Stale/` + `docs-stale/`) - 22 rozjazdy, m.in.:

```
[XD02] Retry.Stale/Backoff.cs:24 Backoff.Delay: <param name="delay"> - w kodzie nie ma takiego parametru
[XD03] Retry.Stale/Backoff.cs:24 Backoff.Delay: kod rzuca ArgumentOutOfRangeException, brak <exception cref="ArgumentOutOfRangeException">
[XD04] Retry.Stale/Backoff.cs:54 Backoff.RunAsync: doc deklaruje TimeoutException, ale kod go nie rzuca
[MD05] README.md:8: `Backoff.MaxDelay` = 60 s, a w kodzie 30000 ms
[MD02] README.md:15: `Backoff.ShouldRetry(httpStatus)` - typ Backoff nie ma skladowej `ShouldRetry`
[MD04] README.md:22: komenda wskazuje `Retry.Sample`, ktorego nie ma
[AD05] ADR-0001-exponential-backoff.md: Konsekwencje bez punktu `Negatywne:` (ADR bez kosztow to reklama)
WYNIK: ROZJAZDY: 22
```

Warto zauważyć, czego tu nie ma: README „nieaktualne" mówi też `Backoff.Delay(attempt, baseDelay, jitter)`
- i **tego walidator nie złapał** (sprawdza nazwę składowej, nie listę argumentów w tekście). Granice niżej.

---

### 4️⃣ Zmierzone: kompilator vs walidator vs wykonywalne przykłady

Kompilator z `GenerateDocumentationFile` to pierwsza linia obrony - i na `Retry.Stale/` rzeczywiście
zgłosił 5 ostrzeżeń (CS1572 x2, CS1573 x2, CS1574). **Nie zgłosił** niczego o wyjątkach, o „502-504"
zamiast 500-599, o `MaxAttempts = 5` w komentarzu ani o README/ADR (nie czyta ich).

[`code/drift_test.py`](code/drift_test.py) wprowadza do czystej kopii po jednym rozjeździe (11 sztuk) i
uruchamia trzy detektory. Prawdziwy output (.NET 10.0.400, Python 3.10.4):

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

| Detektor | Złapał | Co łapie z natury |
|---|---|---|
| 🔎 walidator `docs_check.py` | **9/11** | rozjazd *struktury* i *deklarowanych liczb* (parametry, wyjątki, nazwy, stałe, ścieżki, format ADR) |
| 🛠️ kompilator (XML-doc) | **2/11** | tylko parametry i `cref` w komentarzach `///`; D04 to błąd kompilacji projektu `Retry.Demo`, nie biblioteki |
| ▶️ `Retry.Demo` (przykłady z README wykonywane) | **4/11** | rozjazd *zachowania*: to jedyny detektor, który widzi D10 i D11 |

**Wniosek:** żaden detektor nie łapie wszystkiego, ale **walidator + wykonywane przykłady
razem pokrywają 11/11**, a kompilator nic do tego nie dokłada. Walidator jest ślepy na „zmieniło się
zachowanie, opis słowny został" (D10, D11) - i to jest dokładnie ta klasa błędów, którą ludzie biorą za
„dokumentacja się nie zgadza". Przykład w README musi być **uruchamiany**, nie tylko cytowany.

---

### 5️⃣ Czego to nie dowodzi (i granice walidatora)

> - **Żaden model nie był uruchamiany.** Nie wiem, czy model z `xmldoc_good.txt` zastosuje się do zakazu
>   zgadywania wyjątków albo czy zostawi `BRAK DANYCH`; nie wiem, jak często model z `xmldoc_bad.txt`
>   dopisałby urojone wyjątki. Wartości „9/11" dotyczą rozjazdów, które **ja** wprowadziłem.
> - 11 dryfów to mój wybór, dobrany pod reguły walidatora (część reguł powstała z listy dryfów).
>   Wynik 9/11 jest więc zawyżony względem „prawdziwego" starzenia się dokumentacji.
> - Walidator **nie rozumie treści**: nie wykryje błędnego opisu („zwraca `null`" tam, gdzie zwraca
>   `TimeSpan`), literówki w warunku wyjątku, ani dopisanego argumentu w przykładzie wywołania (widać wyżej: `jitter`).
> - Parser C# to regexy: nie obsługuje atrybutów w sygnaturze, lokalnych funkcji, wyjątków rzucanych
>   przez wywoływane metody pomocnicze (`throw` w innej metodzie) ani `throw ex`. Nie sprawdza też
>   komentarzy dla członków bez `///` (od tego jest CS1591 kompilatora).
> - Reguła MD01 ma listę dozwolonych typów BCL (`BCL_ALLOW`) - nowy typ w dokumencie bywa fałszywym alarmem;
>   przy pierwszym uruchomieniu na `Retry.Demo` (nazwa projektu w backtickach) tak było i dodałem wyjątek.
> - Mały, jednoplikowy przykład; zachowanie na dużym repo (partial, generyki zagnieżdżone, wiele namespace'ów) nieznane.
> - ADR sprawdzam *formalnie*. Czy `Negatywne:` jest sensowne, to ocena człowieka - walidator widzi tylko, że punkt istnieje.
> - Porównanie ze Stryker.NET i prawdziwy model w pętli - nadal przed nami.

---

## Wspólny mianownik

Dokumentacja z modelu jest tak dobra, jak **granica między tym, co wie kod, a tym, co wie człowiek**.
Fakty strukturalne (parametry, wyjątki, stałe) dostarcza skrypt i ten sam skrypt je weryfikuje;
motywację (*dlaczego*) dostarcza człowiek albo model zostawia `BRAK DANYCH`; zachowanie sprawdzają
przykłady, które się wykonują. Prompt bez tych trzech elementów daje dokument, który brzmi dobrze i nie
przechodzi nawet prostego `grep`.

---

## 📎 Jak zweryfikować

Zobacz [`code/README.md`](code/README.md) - komendy i prawdziwy output.

---

<div align="center">

[← wróć do wydania #17 (wszystkie rubryki)](../README.md) · [spis wydań](../../README.md)

</div>
