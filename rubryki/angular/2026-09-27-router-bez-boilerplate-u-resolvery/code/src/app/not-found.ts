import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'app-not-found',
  imports: [RouterLink],
  template: `<h2>404 - nie ma takiego artykułu</h2><a routerLink="/">← lista</a>`,
})
export class NotFound {}
