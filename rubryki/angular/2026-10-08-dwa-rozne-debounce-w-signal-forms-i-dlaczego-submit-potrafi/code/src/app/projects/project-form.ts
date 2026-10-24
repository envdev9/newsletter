import { Component, signal } from '@angular/core';
import { FormField, form } from '@angular/forms/signals';
import { ProjectModel, blurSchema, emptyProject } from './project.schema';

@Component({
  selector: 'app-project-form',
  imports: [FormField],
  template: `
    <div>
      <label for="name">Nazwa projektu</label>
      <input id="name" type="text" [formField]="projectForm.name" />
      <p class="model">Model: <code id="model-name">{{ model().name }}</code></p>
      @if (projectForm.name().pending()) {
        <p class="pending">Sprawdzam unikalność…</p>
      }
      @for (e of projectForm.name().errors(); track e.kind) {
        <p class="error">{{ e.message }}</p>
      }
      @if (projectForm.name().valid()) {
        <p class="ok">Nazwa wolna.</p>
      }
    </div>
    <div>
      <label for="offline">Pracuję offline (bez sprawdzania)</label>
      <input id="offline" type="checkbox" [formField]="projectForm.offline" />
    </div>
  `,
})
export class ProjectForm {
  protected readonly model = signal<ProjectModel>(emptyProject());
  protected readonly projectForm = form(this.model, blurSchema);
}
