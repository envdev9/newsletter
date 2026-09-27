import { Routes } from '@angular/router';
import { articleResolver } from './article.resolver';

export const routes: Routes = [
  { path: '', pathMatch: 'full', loadComponent: () => import('./article-list').then((m) => m.ArticleList) },
  {
    path: 'articles/:id',
    resolve: { article: articleResolver },
    loadComponent: () => import('./article-detail').then((m) => m.ArticleDetail),
  },
  { path: 'not-found', loadComponent: () => import('./not-found').then((m) => m.NotFound) },
  { path: '**', redirectTo: 'not-found' },
];
