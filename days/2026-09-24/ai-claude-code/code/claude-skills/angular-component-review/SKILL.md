---
name: angular-component-review
description: Code review komponentu Angular (zmiany w .ts/.html) pod kątem change detection, zarządzania subskrypcjami, standalone components i typowych pułapek RxJS/signals. Użyj gdy przeglądasz diff/PR dotyczący komponentu Angular albo gdy ktoś prosi o review pliku *.component.ts.
---

# angular-component-review

Checklist do systematycznego review komponentu Angular, wypracowana na podstawie
powtarzających się problemów w PR-ach: wycieki subskrypcji, brak OnPush, mieszanie
signals z RxJS bez potrzeby.

## Jak to zrobić

1. Zacznij od `git diff` / wskazanych plików - nie zgaduj, przeczytaj realny kod
   komponentu (`.ts`, `.html`, ewentualnie `.scss` jeśli zmiana dotyczy layoutu).
2. Przejdź checklistę niżej, punkt po punkcie, per plik.
3. Wynik podaj w formacie tabeli Markdown: `Plik:linia | Kategoria | Problem | Sugerowana poprawka`.
   Pomijaj wiersze bez zastrzeżeń - nie wypisuj "OK" dla każdego punktu.
4. Jeśli plik jest poprawny pod każdym względem, napisz to wprost jednym zdaniem
   zamiast pustej tabeli.

## Checklist

### Change detection
- [ ] Komponent ma `changeDetection: ChangeDetectionStrategy.OnPush` (chyba że jest
      świadomy powód, by tego nie robić - wtedy komentarz w kodzie powinien to
      tłumaczyć).
- [ ] Żadna metoda wywoływana z template nie robi ciężkiej pracy przy każdym cyklu CD
      (np. `.filter()`/`.sort()` bezpośrednio w bindingu zamiast w memoizowanym
      signalu/computed albo pipe).

### Subskrypcje i wycieki pamięci
- [ ] Każdy ręczny `.subscribe()` ma odpowiednik zwolnienia: `takeUntilDestroyed()`,
      `async` pipe w template, albo jawny `Subscription` sprzątany w `ngOnDestroy`.
- [ ] Brak `.subscribe()` wewnątrz `.subscribe()` (nested subscribe) - powinno być
      `switchMap`/`concatMap`/`mergeMap`.

### Standalone / struktura
- [ ] Komponent jest `standalone: true` (chyba że repo jeszcze nie migrowało z
      NgModule - sprawdź konwencję sąsiednich komponentów).
- [ ] `imports: [...]` zawiera tylko to, co faktycznie jest używane w template.

### Signals vs RxJS
- [ ] Stan lokalny, synchroniczny -> `signal`/`computed`, nie `BehaviorSubject` + async
      pipe (chyba że komponent i tak żyje w strumieniu RxJS z reszty aplikacji).
- [ ] `computed()` nie ma efektów ubocznych (żadnych wywołań HTTP/mutacji stanu w
      środku).

### Template
- [ ] `@for` (albo `*ngFor` w starszym kodzie) ma `track`/`trackBy` na kluczu
      biznesowym, nie na indeksie.
- [ ] Brak logiki biznesowej w template poza prostymi bindingami/pipe'ami.
- [ ] `[innerHTML]` tylko z zaufanego/sanityzowanego źródła.

### Dostępność
- [ ] Interaktywne elementy (`div`/`span` z `(click)`) mają odpowiednią rolę/`tabindex`
      albo są zamienione na natywny `button`/`a`.
- [ ] Obrazki i ikony niosące informację mają `alt`/`aria-label`.

## Format odpowiedzi (przykład)

| Plik:linia | Kategoria | Problem | Poprawka |
|---|---|---|---|
| order-list.component.ts:34 | Subskrypcje | `.subscribe()` bez `takeUntilDestroyed()` | Dodaj `takeUntilDestroyed()` albo przejdź na `async` pipe |
| order-list.component.html:12 | Template | `*ngFor` bez `trackBy` | Dodaj `trackBy: trackByOrderId` |
