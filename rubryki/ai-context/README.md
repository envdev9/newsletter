<div align="center">

# 🧠 AI — zarządzanie kontekstem

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-21 | [Delta `ls` z wczoraj działa do pierwszej kompakcji. `ls -R`, projekcja poddrzewa i dwa sposoby na „wiszącą deltę”: leniwy `chain` i drogi `carry`](2026-10-21-delta-ls-z-wczoraj-dziala-do-pierwszej-kompakcji-ls-r/ARTICLE.md) | Delta `ls -R` z projekcją poddrzewa tnie sesję z 30 011 do 3 162 tokenów (9,49×), ale po kompakcji okna 42 z 51 scenariuszy daje wiszące delty; leniwy `chain` (4,45×) i gorliwy `carry` (3,89×) naprawiają to do zera błędów. | [Kod](2026-10-21-delta-ls-z-wczoraj-dziala-do-pierwszej-kompakcji-ls-r/code/) |
| 2026-10-20 | [`ls` to tani wynik, który wraca jak bumerang. Delta katalogu, rzut `-1A` z `-lA` i pokusa „nie wołam, bo wiem”](2026-10-20-ls-to-tani-wynik-ktory-wraca-jak-bumerang-delta-katalogu/ARTICLE.md) | Powtarzane `ls` w sesji agenta: delta katalogu zamiast pełnych kopii daje na 152 wpisach 4,12× mniej tokenów i zero błędów odtworzenia, a polityka „nie wołam `ls`, ufam własnym zdarzeniom” oszczędza 0,1% i myli się po zewnętrznym buildzie. | [Kod](2026-10-20-ls-to-tani-wynik-ktory-wraca-jak-bumerang-delta-katalogu/code/) |
| 2026-10-19 | [Wskaźnik do czegoś, czego już nie ma. Jak „oszczędność” kontekstu po kompakcji zamienia się w ciche kłamstwo](2026-10-19-wskaznik-do-czegos-czego-juz-nie-ma-jak-oszczednosc/ARTICLE.md) | Po kompakcji wskaźnik „bez zmian od tury 11" może wskazywać treść, której już nie ma: najtańsza polityka (2,11×) zgubiła 4 z 14 wyników, a poprawna kosztuje 1,48× — w przemiataniu 108 scenariuszy jedna „prawie dobra" polityka też kłamała. | [Kod](2026-10-19-wskaznik-do-czegos-czego-juz-nie-ma-jak-oszczednosc/code/) |
| 2026-10-14 | [Ten sam plik po raz piąty. Dlaczego „wyrzuć stare odczyty z kontekstu” może wyjść drożej niż ich zostawienie](2026-10-14-ten-sam-plik-po-raz-piaty-dlaczego-wyrzuc-stare-odczyty-z/ARTICLE.md) | Ten sam plik czytany po raz ósmy kosztuje 14 tokenów zamiast 7962 — ale „sprytne" kasowanie starych odczytów (retro) unieważnia cache i wychodzi drożej niż dopisywanie diffów (append): 2,65× taniej wg kosztu ważonego. | [Kod](2026-10-14-ten-sam-plik-po-raz-piaty-dlaczego-wyrzuc-stare-odczyty-z/code/) |
| 2026-10-13 | [„Wycisz pager”, a narzędzie nazywa się `acknowledge_alert`. Jak naprawić wyszukiwarkę narzędzi i jak nie oszukać samego siebie](2026-10-13-wycisz-pager-a-narzedzie-nazywa-sie-acknowledge-alert-jak/ARTICLE.md) | Wyszukiwarka narzędzi zna tylko słowa z nazw: BM25 trafia 34/40 zapytań ze wspólnym słowem i 4/23 bez niego — jak to naprawić synonimami, aliasami i priorem sesji oraz jak nie oszukać się ewaluacją na zbiorze, który widziałeś. | [Kod](2026-10-13-wycisz-pager-a-narzedzie-nazywa-sie-acknowledge-alert-jak/code/) |
| 2026-10-12 | [Notatki sesji: nie dopisuj, składaj. Snapshot stanu zamiast logu](2026-10-12-notatki-sesji-nie-dopisuj-skladaj-snapshot-stanu-zamiast/ARTICLE.md) | Snapshot stanu zamiast dopisywania logu: 300 zdarzeń = 6037 tok., po `fold` 565 tok. (10,7×) — i czytelnik, który ucina log od najstarszych, odtwarza stan na 28–52%, a ze snapshotu na 100% (dane syntetyczne, model niesprawdzany). | [Kod](2026-10-12-notatki-sesji-nie-dopisuj-skladaj-snapshot-stanu-zamiast/code/) |
| 2026-10-08 | [Zadanie 2,8× większe niż okno: gdzie ciąć i co zabrać do następnego okna](2026-10-08-zadanie-2-8-wieksze-niz-okno-gdzie-ciac-i-co-zabrac-do/ARTICLE.md) | Zadanie 2,8× większe niż okno kontekstu: o koszcie decyduje to, co zgubisz przy przejściu między oknami — handoff z samych żywych decyzji bije brak handoffu o 44% (model kosztów na danych syntetycznych). | [Kod](2026-10-08-zadanie-2-8-wieksze-niz-okno-gdzie-ciac-i-co-zabrac-do/code/) |
| 2026-10-07 | [264 narzędzia w kontekście, z których użyjesz 12: eager kontra leniwe ładowanie definicji](2026-10-07-264-narzedzia-w-kontekscie-z-ktorych-uzyjesz-12-eager/ARTICLE.md) | 264 narzędzia MCP kosztują 26 tys. tokenów w każdej turze, a leniwe ładowanie tnie to 5–9×, ale prosta wyszukiwarka gubi ~45% narzędzi przy parafrazach. | [Kod](2026-10-07-264-narzedzia-w-kontekscie-z-ktorych-uzyjesz-12-eager/code/) |
| 2026-10-06 | [Co dać modelowi do ręki, a czego nie: kompresja wyników narzędzi i budżet kontekstu jako kod](2026-10-06-co-dac-modelowi-do-reki-a-czego-nie-kompresja-wynikow/ARTICLE.md) | Każda kompresja wyniku narzędzia jest stratna — oceniaj ją tokenami i przeżywalnością faktów naraz: w teście `head` dawał 88× oszczędności i gubił wszystkie 4 kluczowe fakty, a filtr na JSON-ie zmniejszał 44 tys. tokenów do 80. | [Kod](2026-10-06-co-dac-modelowi-do-reki-a-czego-nie-kompresja-wynikow/code/) |
| 2026-09-27 | [Podatek od każdej tury: ile kosztuje `CLAUDE.md` i serwery MCP, zanim napiszesz pierwsze słowo](2026-09-27-podatek-od-kazdej-tury-ile-kosztuje-claude-md-i-serwery-mcp/ARTICLE.md) | Stały koszt kontekstu: `CLAUDE.md` przycięty z 1242 do 304 tokenów i jeden gadatliwy serwer MCP, który zjada 86% definicji narzędzi — audyt `ctxaudit.py` 13/13, ale na danych syntetycznych (odczyt prawdziwego transkryptu odrzucony). | [Kod](2026-09-27-podatek-od-kazdej-tury-ile-kosztuje-claude-md-i-serwery-mcp/code/) |
| 2026-09-26 | [Kompaktowanie, łańcuchy subagentów i budżet kontekstu: jak przeżyć sesję na 60 tur](2026-09-26-kompaktowanie-lancuchy-subagentow-i-budzet-kontekstu-jak/ARTICLE.md) | 5 wyników narzędzi z 60 dźwiga dwie trzecie kontekstu sesji, a subagent zamiast kompaktowania obniża szczyt kontekstu ponad 4× — metryka „token-tury”, `/compact` i łańcuchy subagentów (liczby z transkryptu syntetycznego). | [Kod](2026-09-26-kompaktowanie-lancuchy-subagentow-i-budzet-kontekstu-jak/code/) |
| 2026-09-24 | [Okno kontekstu: z czego się składa, w jakiej kolejności i jak nim gospodarować](2026-09-24-okno-kontekstu-z-czego-sie-sklada-w-jakiej-kolejnosci-i-jak/ARTICLE.md) | Co się ładuje do okna kontekstu i w jakiej kolejności, kiedy delegować do subagenta, i | [Kod](2026-09-24-okno-kontekstu-z-czego-sie-sklada-w-jakiej-kolejnosci-i-jak/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
