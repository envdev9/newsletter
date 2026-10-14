import { Component } from '@angular/core';
import { SignupForm } from './signup/signup-form';

@Component({
  selector: 'app-root',
  imports: [SignupForm],
  template: `
    <h1>Angular: <code>reset()</code> w trakcie <code>debounce</code> i asynchroniczny walidator CVA</h1>
    <app-signup-form />
  `,
})
export class App {}
