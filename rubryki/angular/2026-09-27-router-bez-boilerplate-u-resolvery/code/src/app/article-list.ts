import { Component, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { ArticlesService } from './articles.service';

@Component({
  selector: 'app-article-list',
  imports: [RouterLink],
  template: `
    <h2>Artykuły</h2>
    <ul>
      @for (a of articles(); track a.id) {
        <li><a [routerLink]="['/articles', a.id]">{{ a.title }}</a></li>
      }
    </ul>
    <p><a routerLink="/articles/999">Link do nieistniejącego artykułu (test resolvera)</a></p>
  `,
})
export class ArticleList {
  protected readonly articles = toSignal(inject(ArticlesService).list(), { initialValue: [] });
}
