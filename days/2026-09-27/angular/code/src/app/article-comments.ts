import { Component, inject, input } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { switchMap } from 'rxjs';
import { toObservable } from '@angular/core/rxjs-interop';
import { ArticlesService } from './articles.service';

/** "Ciężki" komponent - ładowany dopiero przez @defer (osobny chunk JS). */
@Component({
  selector: 'app-article-comments',
  template: `
    <ul class="comments">
      @for (c of comments(); track c) {
        <li>{{ c }}</li>
      } @empty {
        <li>Ładuję komentarze...</li>
      }
    </ul>
  `,
})
export class ArticleComments {
  readonly articleId = input.required<number>();
  private readonly service = inject(ArticlesService);
  protected readonly comments = toSignal(
    toObservable(this.articleId).pipe(switchMap((id) => this.service.comments(id))),
    { initialValue: [] as string[] },
  );
}
