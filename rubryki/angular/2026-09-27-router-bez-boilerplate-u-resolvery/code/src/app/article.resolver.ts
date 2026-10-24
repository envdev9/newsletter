import { inject } from '@angular/core';
import { RedirectCommand, ResolveFn, Router } from '@angular/router';
import { map } from 'rxjs';
import { Article, ArticlesService } from './articles.service';

/**
 * Resolver: router poczeka na dane ZANIM aktywuje trasę.
 * Nieistniejący lub nieliczbowy id -> RedirectCommand na /not-found
 * (zamiast rzucać wyjątek i zostawiać nawigację w połowie).
 */
export const articleResolver: ResolveFn<Article> = (route) => {
  const router = inject(Router);
  const notFound = new RedirectCommand(router.parseUrl('/not-found'));
  const id = Number(route.paramMap.get('id'));
  if (!Number.isInteger(id)) {
    return notFound;
  }
  return inject(ArticlesService)
    .get(id)
    .pipe(map((article) => article ?? notFound));
};
