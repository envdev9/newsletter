import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet],
  template: `
    <h1>Angular: router (resolver + input binding) i &#64;defer</h1>
    <router-outlet />
  `,
})
export class App {}
