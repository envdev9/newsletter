import { Component, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Observable, Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged, switchMap, tap } from 'rxjs/operators';

interface Repo {
  name: string;
}

// Symulacja wywołania HTTP (w realnym kodzie: httpClient.get<Repo[]>(...)).
// Celowo zwraca Observable, nie Promise - żeby switchMap mógł ją anulować.
function fakeSearchApi(query: string): Observable<Repo[]> {
  return new Observable<Repo[]>((subscriber) => {
    const timer = setTimeout(() => {
      subscriber.next(
        query.trim()
          ? [`${query}-app`, `${query}-core`, `${query}-utils`].map((name) => ({ name }))
          : [],
      );
      subscriber.complete();
    }, 300);
    return () => clearTimeout(timer);
  });
}

@Component({
  selector: 'app-search',
  templateUrl: './search.html',
})
export class Search {
  protected readonly loading = signal(false);

  private readonly query$ = new Subject<string>();

  // Tu jest właściwe miejsce na RxJS, nie na signal(). Strumień wpisywania tekstu
  // jest ASYNCHRONICZNY, WIELOKROTNY w czasie i wymaga ANULOWANIA poprzedniego
  // zapytania, gdy przyjdzie nowe - signal() sam z siebie nie ma pojęcia o czasie
  // ani o anulowaniu, do tego zawsze będzie służył RxJS. Operatory, które REALNIE
  // przydają się w takim kodzie na co dzień:
  //   - debounceTime  - nie strzelaj przy każdym naciśnięciu klawisza, poczekaj na ciszę
  //   - distinctUntilChanged - nie strzelaj drugi raz o to samo
  //   - switchMap     - nowe zapytanie ANULUJE poprzednie w locie (kluczowe przy search-as-you-type)
  //   - catchError    - błąd jednego zapytania nie może ubić całego strumienia
  //   - combineLatest / withLatestFrom - łączenie kilku źródeł zmieniających się niezależnie
  //   - takeUntilDestroyed - automatyczne odsubskrybowanie ręcznej subskrypcji przy zniszczeniu komponentu
  // toSignal() na końcu to most z powrotem do świata signals - template czyta
  // zwykły signal (`results()`), nie musi nic wiedzieć o RxJS w środku.
  protected readonly results = toSignal(
    this.query$.pipe(
      tap(() => this.loading.set(true)),
      debounceTime(300),
      distinctUntilChanged(),
      switchMap((query) => fakeSearchApi(query).pipe(tap(() => this.loading.set(false)))),
    ),
    { initialValue: [] as Repo[] },
  );

  protected onInput(value: string): void {
    this.query$.next(value);
  }
}
