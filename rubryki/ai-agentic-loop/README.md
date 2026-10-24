<div align="center">

# ⚙️ AI — agentic loop

### TECH PRASÓWKA — wszystkie artykuły rubryki, najnowsze na górze

</div>

---

Każdy artykuł to osobny folder `<data>-<tytuł>/` z `ARTICLE.md` i pełnym, uruchamialnym
kodem w `code/`. Kolejne artykuły podnoszą poziom — postęp rubryki jest w
[`STATE.md`](../../STATE.md).

| Data | Artykuł | W skrócie | Kod |
|------|---------|-----------|-----|
| 2026-10-24 | [Token w dzienniku WAL: czytelnik ogradza zombie, ale nie cofa skutków](2026-10-24-token-w-dzienniku-wal-czytelnik-ogradza-zombie-ale-nie-cofa/ARTICLE.md) | Dziennik WAL z tokenem w każdym rekordzie: `fold` ogradza zombie po `SIGCONT`, ale zdublowanych skutków nie cofnie, a tryb „zamiar przed skutkiem" zamienia duplikaty w opóźnienie albo lukę. | [Kod](2026-10-24-token-w-dzienniku-wal-czytelnik-ogradza-zombie-ale-nie-cofa/code/) |
| 2026-10-18 | [Zamrożony właściciel: dzierżawa, heartbeat i token ogrodzeniowy](2026-10-18-zamrozony-wlasciciel-dzierzawa-heartbeat-i-token/ARTICLE.md) | Co, gdy właściciel blokady nie umiera, tylko zamarza (`SIGSTOP`)? `flock` trzyma bez końca, dzierżawa z TTL przechodzi na drugiego w 0,54 s — ale dopiero fencing token sprawdzany przez sam zasób zatrzymuje zapisy zombie (3 → 1 → 0). | [Kod](2026-10-18-zamrozony-wlasciciel-dzierzawa-heartbeat-i-token/code/) |
| 2026-10-17 | [Dwóch nadzorców, jeden dziennik: kto trzyma pióro?](2026-10-17-dwoch-nadzorcow-jeden-dziennik-kto-trzyma-pioro/ARTICLE.md) | Dwóch nadzorców na jednym dzienniku podwaja efekty i nikt tego nie widzi w logu — `flock` na osobnym pliku (z czterema pułapkami zmierzonymi na prawdziwych `SIGKILL`) daje dokładnie jedno pióro. | [Kod](2026-10-17-dwoch-nadzorcow-jeden-dziennik-kto-trzyma-pioro/code/) |
| 2026-10-11 | [Gdy hash drzewa liczy git, a archiwum dziennika składa się z powrotem w jedną oś czasu](2026-10-11-gdy-hash-drzewa-liczy-git-a-archiwum-dziennika-sklada-sie-z/ARTICLE.md) | Hash drzewa repo z `git write-tree` zamiast własnego (przy 5000 plików ~8× szybszy z trwałym indeksem), a przy okazji pułapka: crash w kompaktowaniu sprawia, że archiwum i żywy dziennik to ten sam inode — oś zdarzeń pokazuje 79 zdarzeń zamiast 61. | [Kod](2026-10-11-gdy-hash-drzewa-liczy-git-a-archiwum-dziennika-sklada-sie-z/code/) |
| 2026-10-10 | [Postęp mierzy się w kodzie, nie w tekście błędu — i pamięć agenta nie może rosnąć bez końca](2026-10-10-postep-mierzy-sie-w-kodzie-nie-w-tekscie-bledu-i-pamiec/ARTICLE.md) | Agent, który po raz piąty puszcza testy na tym samym kodzie, ma tekst błędu za każdym razem inny, więc stary detektor milczy — hash drzewa repo zatrzymuje go po 3 porażkach, a snapshoty zmniejszają dziennik prawie 6 razy bez zmiany wyniku. | [Kod](2026-10-10-postep-mierzy-sie-w-kodzie-nie-w-tekscie-bledu-i-pamiec/code/) |
| 2026-10-08 | [Dziennik ma początek, a nie miał końca: zamknięcie biegu, zegar po restarcie i człowiek jako rekord](2026-10-08-dziennik-ma-poczatek-a-nie-mial-konca-zamkniecie-biegu/ARTICLE.md) | Urwany ostatni wiersz dziennika potrafił po cichu zgubić resztę historii agenta — naprawa, zamknięcie biegu i wznawialny budżet czasu (bez niego restart kosztował 30,6 s snu zamiast 11,2 s). | [Kod](2026-10-08-dziennik-ma-poczatek-a-nie-mial-konca-zamkniecie-biegu/code/) |
| 2026-10-07 | [Pętla, która umie się zatrzymać i wznowić: budżet, wykrywanie zapętlenia, retry, idempotencja](2026-10-07-petla-ktora-umie-sie-zatrzymac-i-wznowic-budzet-wykrywanie/ARTICLE.md) | Pętla agentowa musi mieć warunki wyjścia poza modelem: budżet, wykrywanie zapętlenia, retry z jitterem i dziennik z kluczem idempotencji — dzięki nim crash w połowie kroku nie wysyła maila dwa razy. | [Kod](2026-10-07-petla-ktora-umie-sie-zatrzymac-i-wznowic-budzet-wykrywanie/code/) |
| 2026-10-06 | [Równoległe agenty bez bijatyki: `git worktree` jako izolacja systemu plików](2026-10-06-rownolegle-agenty-bez-bijatyki-git-worktree-jako-izolacja/ARTICLE.md) | Dwóch agentów w jednym katalogu to ciche nadpisanie cudzej zmiany bez błędu — `git worktree` daje każdemu własny katalog, `HEAD` i indeks, a konflikt wychodzi jawnie dopiero przy merge. | [Kod](2026-10-06-rownolegle-agenty-bez-bijatyki-git-worktree-jako-izolacja/code/) |
| 2026-09-29 | [Kto wybiera skill? Nie hook, nie Ty — model, po samym opisie](2026-09-29-kto-wybiera-skill-nie-hook-nie-ty-model-po-samym-opisie/ARTICLE.md) | Kto wybiera skill? Nie hook, nie harness — model, wyłącznie na podstawie `description`; symulacja pokazuje, jak identyczna procedura z lepiej napisanym opisem łapie parafrazę zadania, a z gorszym opisem daje totalny miss. | [Kod](2026-09-29-kto-wybiera-skill-nie-hook-nie-ty-model-po-samym-opisie/code/) |
| 2026-09-27 | [Wachlarz subagentów, uprawnienia w trybie bez człowieka i bramka CI](2026-09-27-wachlarz-subagentow-uprawnienia-w-trybie-bez-czlowieka-i/ARTICLE.md) | Wachlarz równoległych subagentów ze scalaniem wyników, pułapka uprawnień (`dotnet test && git push` przechodzi przez `dotnet test*`) i bramka CI wokół `claude -p` — 19/19 lokalnych testów, ale samo `claude` niezweryfikowane. | [Kod](2026-09-27-wachlarz-subagentow-uprawnienia-w-trybie-bez-czlowieka-i/code/) |
| 2026-09-26 | [Własny subagent, pętla z weryfikacją i hooki, które przeżywają kompaktowanie](2026-09-26-wlasny-subagent-petla-z-weryfikacja-i-hooki-ktore/ARTICLE.md) | Subagent z odebranym `Edit` i `Bash`, pętla, w której o sukcesie decyduje exit code testów, a nie słowo agenta, i hooki `PreCompact`/`SessionStart` przenoszące listę zadań przez kompaktowanie kontekstu — skrypty zweryfikowane lokalnie, żywa sesja nie. | [Kod](2026-09-26-wlasny-subagent-petla-z-weryfikacja-i-hooki-ktore/code/) |
| 2026-09-25 | [Drzwi wejściowe i wyjściowe pętli: `UserPromptSubmit`, `Stop`, `SubagentStop` — i co, gdy hooków jest kilka](2026-09-25-drzwi-wejsciowe-i-wyjsciowe-petli-userpromptsubmit-stop/ARTICLE.md) | `UserPromptSubmit`, `Stop` i `SubagentStop` w praktyce (bramka „testy zielone"), co się dzieje, gdy na jednym evencie jest kilka hooków (równolegle, bez kolejności), oraz własny skill `changelog-entry` od zera. | [Kod](2026-09-25-drzwi-wejsciowe-i-wyjsciowe-petli-userpromptsubmit-stop/code/) |
| 2026-09-24 | [Agenci, skille, komendy, hooki - jak to się w ogóle ze sobą łączy](2026-09-24-agenci-skille-komendy-hooki-jak-to-sie-w-ogole-ze-soba-laczy/ARTICLE.md) | Jeden mechanizm, trzy sposoby żeby do niego coś dopisać — kto naciska spust i w jakiej | [Kod](2026-09-24-agenci-skille-komendy-hooki-jak-to-sie-w-ogole-ze-soba-laczy/code/) |
<!-- kolejne wiersze dopisywane automatycznie, najnowsze na górze -->

---

<div align="center">

[← spis rubryk](../../README.md)

</div>
