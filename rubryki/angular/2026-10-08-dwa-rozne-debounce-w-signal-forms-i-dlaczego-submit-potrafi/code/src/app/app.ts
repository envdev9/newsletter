import { Component } from '@angular/core';
import { ProjectForm } from './projects/project-form';

@Component({
  selector: 'app-root',
  imports: [ProjectForm],
  template: `
    <h1>Angular: <code>debounce()</code> na polu vs <code>debounce</code> w <code>validateHttp</code></h1>
    <app-project-form />
  `,
})
export class App {}
