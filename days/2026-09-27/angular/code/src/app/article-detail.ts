import { Component, computed, input } from '@angular/core';
import { RouterLink } from '@angular/router';
import { ArticleComments } from './article-comments';
import { Article } from './articles.service';

/**
 * Wszystkie trzy inputy wypełnia ROUTER dzięki withComponentInputBinding():
 *  - id      <- parametr ścieżki  /articles/:id
 *  - tab     <- query param       ?tab=comments
 *  - article <- wynik resolvera   resolve: { article: articleResolver }
 */
@Component({
  selector: 'app-article-detail',
  imports: [RouterLink, ArticleComments],
  template: `
    <a routerLink="/">← lista</a>
    <h2>{{ article().title }} <small>(id z URL: {{ id() }})</small></h2>
    <p>{{ article().body }}</p>

    @if (showComments()) {
      @defer (when showComments()) {
        <app-article-comments [articleId]="article().id" />
      } @loading (minimum 10ms) {
        <p class="loading">Wczytuję moduł komentarzy...</p>
      } @error {
        <p class="error">Nie udało się wczytać komentarzy.</p>
      }
    } @else {
      <a [routerLink]="[]" [queryParams]="{ tab: 'comments' }">Pokaż komentarze</a>
    }
  `,
})
export class ArticleDetail {
  readonly id = input.required<string>();
  readonly article = input.required<Article>();
  // Opcjonalny query param: gdy go brak w URL, router ustawia undefined.
  readonly tab = input<string | undefined>();

  protected readonly showComments = computed(() => this.tab() === 'comments');
}
