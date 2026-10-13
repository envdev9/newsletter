import { Component } from '@angular/core';
import { SettingsForm } from './settings/settings-form';

@Component({
  selector: 'app-root',
  imports: [SettingsForm],
  template: `
    <h1>Angular: <code>FormCheckboxControl</code> i <code>ControlValueAccessor</code> pod <code>[formField]</code></h1>
    <app-settings-form />
  `,
})
export class App {}
