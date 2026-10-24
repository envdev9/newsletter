import { Component, inject } from '@angular/core';
import { injectDispatch } from '@ngrx/signals/events';
import { ActivityLogStore } from './activity-log.store';
import { tasksPageEvents } from './tasks.events';
import { TasksStore } from './tasks.store';

@Component({
  selector: 'app-tasks-page',
  template: `
    <button id="load" (click)="dispatch.opened()">Wczytaj</button>
    <input #title id="title" />
    <button id="add" (click)="dispatch.added(title.value); title.value = ''">Dodaj</button>

    @if (store.loading()) { <p id="loading">Ładowanie...</p> }
    @if (store.error(); as e) { <p id="error" class="error">Błąd: {{ e }}</p> }

    <ul>
      @for (t of store.tasks(); track t.id) {
        <li>
          <label>
            <input type="checkbox" [checked]="t.done" (change)="dispatch.toggled(t.id)" />
            {{ t.title }}
          </label>
        </li>
      }
    </ul>
    <p id="count">Zrobione: {{ store.doneCount() }} / {{ store.tasks().length }}</p>

    <h3>Dziennik zdarzeń</h3>
    <ol id="log">
      @for (entry of logStore.log(); track $index) { <li>{{ entry }}</li> }
    </ol>
  `,
})
export class TasksPage {
  readonly store = inject(TasksStore);
  readonly logStore = inject(ActivityLogStore);
  readonly dispatch = injectDispatch(tasksPageEvents);
}
