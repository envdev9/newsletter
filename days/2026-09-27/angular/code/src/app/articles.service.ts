import { Injectable } from '@angular/core';
import { Observable, delay, of } from 'rxjs';

export interface Article {
  id: number;
  title: string;
  body: string;
}

const ARTICLES: Article[] = [
  { id: 1, title: 'Signals od zera', body: 'signal, computed, effect.' },
  { id: 2, title: 'Signal store', body: 'withState, withComputed, withMethods.' },
  { id: 3, title: 'Router i resolvery', body: 'Dane przed wejściem na trasę.' },
];

/** Udaje backend: dane w pamięci + sztuczne opóźnienie (bez HTTP, żeby skupić się na routerze). */
@Injectable({ providedIn: 'root' })
export class ArticlesService {
  readonly latencyMs = 50;

  list(): Observable<Article[]> {
    return of(ARTICLES).pipe(delay(this.latencyMs));
  }

  get(id: number): Observable<Article | undefined> {
    return of(ARTICLES.find((a) => a.id === id)).pipe(delay(this.latencyMs));
  }

  comments(articleId: number): Observable<string[]> {
    return of([`Komentarz A do #${articleId}`, `Komentarz B do #${articleId}`]).pipe(delay(this.latencyMs));
  }
}
