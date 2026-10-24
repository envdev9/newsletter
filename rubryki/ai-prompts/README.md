<div align="center">

# ✍️ AI — prompty dla developera

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-24 | [Układ promptu pod cache prefiksu: w łańcuchu z #18 kroki 2 i 3 mają 6 wspólnych znaków; po przestawieniu 940 - i dopiero od ~8-krotnie większego kodu to się opłaca](2026-10-24-uklad-promptu-pod-cache-prefiksu-w-lancuchu-z-18-kroki-2-i/ARTICLE.md) | Układ promptu pod cache prefiksu: w łańcuchu z #18 kroki 2 i 3 mają 6 wspólnych znaków, po przestawieniu 940 — ale zwrot kosztowy (~0,7–0,8x) pojawia się dopiero przy większym kodzie, a jedna linia `Krok n:` na górze wszystko kasuje. | [Kod](2026-10-24-uklad-promptu-pod-cache-prefiksu-w-lancuchu-z-18-kroki-2-i/code/) |
| 2026-10-18 | [Ile kosztuje łańcuch promptów: 1,9x droższy od jednego promptu na małym kodzie, 0,6x na dużym - i dlaczego to drugie jest liczbą z modelu, nie z pomiaru](2026-10-18-ile-kosztuje-lancuch-promptow-1-9x-drozszy-od-jednego/ARTICLE.md) | Łańcuch promptów kosztuje ok. 1,9–2× więcej tokenów niż jeden prompt, a fail-fast oszczędza 33% — ale tylko tam, gdzie odrzucenie pada w krokach 1–2; do tego próg, od którego łańcuch i tak się opłaca (szacunek na długościach, bez modelu). | [Kod](2026-10-18-ile-kosztuje-lancuch-promptow-1-9x-drozszy-od-jednego/code/) |
| 2026-10-17 | [Walidator odpowiedzi modelu na Roslynie: 10 fałszywych alarmów regexu, 5 przepuszczonych zmyśleń i jedna rzecz, w której regex wygrywa](2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/ARTICLE.md) | Regex „widzi" w kodzie C# to, co wygląda jak deklaracja: 5 zmyślonych symboli przeszło, 10 prawdziwych odrzucił — Roslyn zrobił 24/25 poprawnych decyzji i oddaje błąd kompilatora gotowy do promptu naprawczego. | [Kod](2026-10-17-walidator-odpowiedzi-modelu-na-roslynie-10-falszywych/code/) |
| 2026-10-11 | [Jeden wielki prompt vs łańcuch trzech: kontrakt między krokami, który odrzuca zmyślone symbole, rozrost zakresu i „naprawione" testy](2026-10-11-jeden-wielki-prompt-vs-lancuch-trzech-kontrakt-miedzy/ARTICLE.md) | Zamiast mega-promptu „napraw i upewnij się, że testy przechodzą" — łańcuch triaż → plan → patch z kontraktem między krokami; na 7 nagraniach 0 fałszywych zielonych vs 2 w wersji bez kontraktów (uczciwie: bez prawdziwego modelu, to test łańcucha, nie LLM-a). | [Kod](2026-10-11-jeden-wielki-prompt-vs-lancuch-trzech-kontrakt-miedzy/code/) |
| 2026-10-10 | [Dokumentacja, która kłamie po tygodniu: prompty do XML-doc, README i ADR z walidatorem zgodności z kodem](2026-10-10-dokumentacja-ktora-klamie-po-tygodniu-prompty-do-xml-doc/ARTICLE.md) | Dokumentacja z modelu zmyśla parametry i starzeje się po cichu — dziś fakty o kodzie wchodzą do promptu ze skryptu, a ten sam skrypt waliduje wynik; zmierzone na 11 rozjazdach: walidator 9/11, kompilator 2/11. | [Kod](2026-10-10-dokumentacja-ktora-klamie-po-tygodniu-prompty-do-xml-doc/code/) |
| 2026-10-07 | [„Napisz testy" to za mało: prompty do generowania testów, które sprawdzamy mutacjami](2026-10-07-napisz-testy-to-za-malo-prompty-do-generowania-testow-ktore/ARTICLE.md) | Zielone testy wygenerowane przez model niczego nie dowodzą — 5 „naiwnych" testów zabiło 14% mutantów, a 24 napisane wg dobrego promptu 86%; dziś prompt z kontraktem, brzegami i zakazem słabych asercji oraz pętla zwrotna z przeżytych mutantów. | [Kod](2026-10-07-napisz-testy-to-za-malo-prompty-do-generowania-testow-ktore/code/) |
| 2026-09-27 | [Refaktoryzacja, migracja, few-shot i CLAUDE.md: prompty, które pracują na siatce bezpieczeństwa](2026-09-27-refaktoryzacja-migracja-few-shot-i-claude-md-prompty-ktore/ARTICLE.md) | Jak prosić o refaktoryzację i migrację (Newtonsoft → System.Text.Json) tak, by nic się po cichu nie zmieniło: testy charakteryzujące, few-shot z walidowanym schematem i CLAUDE.md jako trwały prompt — lint 8/8, golden master 0 vs 37 różnic; jakość odpowiedzi modelu niezweryfikowana. | [Kod](2026-09-27-refaktoryzacja-migracja-few-shot-i-claude-md-prompty-ktore/code/) |
| 2026-09-26 | [Prompt do debugowania i code review: wklej dowód, poproś o hipotezy, zdefiniuj skalę uwag](2026-09-26-prompt-do-debugowania-i-code-review-wklej-dowod-popros-o/ARTICLE.md) | Zamiast „napraw błąd” wklej stack trace, poproś o uszeregowane hipotezy przed poprawką i zdefiniuj skalę uwag w review — plus lint promptów, który łapie braki, ale (uczciwie) nie dowodzi jakości odpowiedzi modelu. | [Kod](2026-09-26-prompt-do-debugowania-i-code-review-wklej-dowod-popros-o/code/) |
| 2026-09-24 | [Zły i dobry prompt obok siebie: 5 par z komentarzem, dlaczego jeden działa, a drugi nie](2026-09-24-zly-i-dobry-prompt-obok-siebie-5-par-z-komentarzem-dlaczego/ARTICLE.md) | 5 par zły/dobry prompt z komentarzem dlaczego — zweryfikowane skryptem, nie na wyczucie. | [Kod](2026-09-24-zly-i-dobry-prompt-obok-siebie-5-par-z-komentarzem-dlaczego/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
