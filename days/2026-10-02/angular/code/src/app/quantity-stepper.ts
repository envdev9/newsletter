import { Component, ElementRef, input, model, output, signal, viewChild } from '@angular/core';
import type { FormValueControl, ValidationError } from '@angular/forms/signals';

/**
 * Własny "kontrolek" formularza - ZAMIAST natywnego `<input type="number">`. Wydanie #7 (30.09)
 * zaimplementowało tylko `value`/`disabled`/`min`/`max` z kontraktu `FormValueControl<TValue>`.
 * Dziś dochodzi RESZTA opcjonalnego kontraktu `FormUiControl`:
 *
 *  - `errors` (`InputSignal`) - Signal Forms wstrzykuje tu aktualne błędy pola; renderujemy je
 *    WEWNĄTRZ komponentu zamiast w szablonie hosta jak poprzednio.
 *  - `touched` (`InputSignal`) - stan "touched" pola, używany tu wyłącznie do stylu (czerwona
 *    ramka po pierwszej interakcji, zanim jeszcze błąd się pojawi).
 *  - `touch` (`OutputRef<void>`) - WYJŚCIE: to KONTROLKA informuje formularz "użytkownik
 *    skończył interakcję, oznacz mnie jako touched". Stepper nie ma natywnego `blur` w sensie
 *    pola tekstowego, więc emitujemy `touch` po każdym kliknięciu +/- (pierwsza interakcja =
 *    "dotknięte" - inna semantyka niż `blur` na `<input>`, ale sensowna dla przycisków).
 *  - `focus()` - Signal Forms wywołuje tę metodę zamiast domyślnego fokusowania hosta; tu
 *    fokusujemy przycisk "+".
 *  - `reset()` - wywoływany, gdy ktoś zawoła `fieldState.reset()` na polu/przodku pola. Stepper
 *    nie ma oddzielnego bufora tekstu (w odróżnieniu od `PriceInput`), więc nie ma czego
 *    synchronizować - zostaje tylko jako DOWÓD w teście, że Signal Forms faktycznie woła tę
 *    metodę (licznik `resetCallCount`).
 */
@Component({
  selector: 'app-quantity-stepper',
  template: `
    <div class="stepper" [class.is-disabled]="disabled()" [class.is-touched]="touched()">
      <button
        type="button"
        class="step-btn"
        (click)="decrement()"
        [disabled]="disabled() || !canDecrement()"
      >
        −
      </button>
      <span class="qty-value">{{ value() }}</span>
      <button
        #incBtn
        type="button"
        class="step-btn"
        (click)="increment()"
        [disabled]="disabled() || !canIncrement()"
      >
        +
      </button>
    </div>
    @for (e of errors(); track e.kind) {
      <p class="error">{{ e.message }}</p>
    }
  `,
})
export class QuantityStepper implements FormValueControl<number> {
  readonly value = model.required<number>();
  readonly disabled = input<boolean>(false);
  readonly min = input<number | undefined>(undefined);
  readonly max = input<number | undefined>(undefined);
  readonly errors = input<readonly ValidationError.WithOptionalFieldTree[]>([]);
  readonly touched = input<boolean>(false);
  readonly touch = output<void>();

  // Liczniki WYŁĄCZNIE do weryfikacji w testach.
  protected readonly focusCallCount = signal(0);
  protected readonly resetCallCount = signal(0);

  private readonly incBtnRef = viewChild.required<ElementRef<HTMLButtonElement>>('incBtn');

  protected canDecrement(): boolean {
    return this.min() === undefined || this.value() > this.min()!;
  }
  protected canIncrement(): boolean {
    return this.max() === undefined || this.value() < this.max()!;
  }
  protected increment(): void {
    if (this.canIncrement()) {
      this.value.update((v) => v + 1);
    }
    this.touch.emit();
  }
  protected decrement(): void {
    if (this.canDecrement()) {
      this.value.update((v) => v - 1);
    }
    this.touch.emit();
  }

  focus(options?: FocusOptions): void {
    this.focusCallCount.update((n) => n + 1);
    this.incBtnRef().nativeElement.focus(options);
  }

  reset(): void {
    this.resetCallCount.update((n) => n + 1);
  }
}
