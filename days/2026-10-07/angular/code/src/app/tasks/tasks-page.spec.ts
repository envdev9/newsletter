import { TestBed } from '@angular/core/testing';
import { TasksPage } from './tasks-page';

describe('TasksPage (DOM)', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('Wczytaj -> Ładowanie... -> lista; Dodaj -> nowa pozycja; dziennik pokazuje typy zdarzeń', async () => {
    const fixture = TestBed.createComponent(TasksPage);
    const el = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();

    el.querySelector<HTMLButtonElement>('#load')!.click();
    fixture.detectChanges();
    expect(el.querySelector('#loading')).toBeTruthy();

    await vi.advanceTimersByTimeAsync(200);
    fixture.detectChanges();
    expect(el.querySelector('#loading')).toBeNull();
    expect(el.querySelectorAll('li input[type=checkbox]').length).toBe(2);
    expect(el.querySelector('#count')!.textContent).toContain('Zrobione: 1 / 2');

    const title = el.querySelector<HTMLInputElement>('#title')!;
    title.value = 'Nowe zadanie';
    el.querySelector<HTMLButtonElement>('#add')!.click();
    fixture.detectChanges();
    expect(el.querySelector('#count')!.textContent).toContain('Zrobione: 1 / 3');

    const log = Array.from(el.querySelectorAll('#log li')).map((li) => li.textContent);
    expect(log).toEqual([
      '[Tasks Page] opened',
      '[Tasks API] loadedSuccess',
      '[Tasks Page] added',
    ]);
  });
});
