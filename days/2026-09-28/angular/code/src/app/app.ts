import { Component } from '@angular/core';
import { RegistrationForm } from './registration-form';

@Component({
  selector: 'app-root',
  imports: [RegistrationForm],
  template: `
    <h1>Angular: Signal Forms + &#64;angular/core <code>resource()</code></h1>
    <app-registration-form />
  `,
})
export class App {}
