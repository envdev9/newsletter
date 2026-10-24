import { Component } from '@angular/core';
import { TasksPage } from './tasks/tasks-page';

@Component({
  selector: 'app-root',
  imports: [TasksPage],
  template: `
    <h1>Angular: SignalStore Events - zdarzenia, reduktory i efekty</h1>
    <app-tasks-page />
  `,
})
export class App {}
