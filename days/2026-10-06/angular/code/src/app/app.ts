import { Component } from '@angular/core';
import { ProjectForm } from './projects/project-form';

@Component({
  selector: 'app-root',
  imports: [ProjectForm],
  template: `
    <h1>Angular: <code>validateHttp</code> - asynchroniczna walidacja pola przez HTTP</h1>
    <app-project-form />
  `,
})
export class App {}
