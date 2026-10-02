import { Component, ElementRef, input, model, output, signal, viewChild } from '@angular/core';
import type { FormValueControl, ParseResult, ValidationError } from '@angular/forms/signals';
import { transformedValue } from '@angular/forms/signals';

/** Formatuje liczbę jako cenę w stylu polskim: przecinek dziesiętny, zawsze 2 miejsca. */
export function formatPrice(value: number): string {
  return value.toFixed(2).replace('.', ',');
}

/**
 * Własny `FormValueControl<number>` - cena wpisywana jako TEKST ("12,50", przecinek jak w
 * polskim UI), a nie natywny `<input type="number">` (który i tak nie rozumie przecinka
 * dziesiętnego - tylko kropkę). Dwie rzeczy, których nie było w `QuantityStepper` z wydania #7
 * (30.09):
 *
 *  1. `transformedValue()` - para sygnałów "surowy tekst UI" <-> "wartość modelu" z funkcjami
 *     `parse`/`format`. Błędny tekst (np. "abc") NIE crashuje i NIE trafia do modelu - `parse()`
 *     zwraca `{ error }` zamiast `{ value }`, a Signal Forms zgłasza ten błąd na polu
 *     AUTOMATYCZNIE (bez żadnego dodatkowego kodu łączącego), obok zwykłych błędów schematu
 *     (np. `min()`) - patrz artykuł, sekcja 1.
 *  2. PEŁNY kontrakt `FormUiControl`, nie tylko `value`/`disabled`: `errors` (renderowane
 *     WEWNĄTRZ kontrolka), `touched` (styl obramowania), `touch` (emitowany na `blur` - Signal
 *     Forms oznacza pole jako touched), `focus()` (przenosi focus na natywny `<input>` w środku),
 *     `reset()` (wywoływany przez Signal Forms przy `fieldState.reset()` - patrz artykuł, sekcja 2).
 */
@Component({
  selector: 'app-price-input',
  template: `
    <div class="price-field" [class.is-touched]="touched()" [class.has-error]="errors().length > 0">
      <input
        #nativeInput
        type="text"
        inputmode="decimal"
        class="price-native"
        [value]="rawValue()"
        [disabled]="disabled()"
        (input)="onInput($event)"
        (blur)="onBlur()"
      />
      <span class="suffix">zł</span>
    </div>
    @for (e of errors(); track e.kind) {
      <p class="error">{{ e.message }}</p>
    }
  `,
})
export class PriceInput implements FormValueControl<number> {
  readonly value = model.required<number>();
  readonly disabled = input<boolean>(false);
  readonly errors = input<readonly ValidationError.WithOptionalFieldTree[]>([]);
  readonly touched = input<boolean>(false);
  readonly touch = output<void>();

  // Liczniki WYŁĄCZNIE do weryfikacji w testach - dowód, że Signal Forms faktycznie wywołuje
  // focus()/reset() na tym komponencie, a nie tylko że typy się zgadzają.
  protected readonly focusCallCount = signal(0);
  protected readonly resetCallCount = signal(0);

  private readonly nativeInputRef = viewChild.required<ElementRef<HTMLInputElement>>('nativeInput');

  /**
   * `rawValue` to osobny sygnał "tekstu w inpucie", zsynchronizowany z `value` (modelem typu
   * `number`) przez `parse`/`format`. Zob. artykuł sekcja 1 - tu sama definicja reguł.
   */
  protected readonly rawValue = transformedValue(this.value, {
    parse: (raw: string): ParseResult<number> => {
      const trimmed = raw.trim();
      if (trimmed === '') {
        return { error: { kind: 'price-required', message: 'Podaj cenę' } };
      }
      const normalized = trimmed.replace(/\s/g, '').replace(',', '.');
      const parsed = Number(normalized);
      if (!Number.isFinite(parsed)) {
        return { error: { kind: 'price-parse', message: `"${raw}" nie jest poprawną ceną (np. 12,50)` } };
      }
      if (parsed < 0) {
        return { error: { kind: 'price-negative', message: 'Cena nie może być ujemna' } };
      }
      return { value: Math.round(parsed * 100) / 100 };
    },
    format: (value) => formatPrice(value),
  });

  protected onInput(event: Event): void {
    this.rawValue.set((event.target as HTMLInputElement).value);
  }

  protected onBlur(): void {
    this.touch.emit();
  }

  focus(options?: FocusOptions): void {
    this.focusCallCount.update((n) => n + 1);
    this.nativeInputRef().nativeElement.focus(options);
  }

  reset(): void {
    this.resetCallCount.update((n) => n + 1);
    // Celowo PUSTE poza licznikiem: cofnięcie wyświetlanego tekstu do sformatowanej wartości
    // modelu i wyczyszczenie błędów parsowania dzieje się SAMO, bo `transformedValue()` wpina
    // się pod `reset()` pola przez wstrzyknięty token integracji - zob. artykuł, sekcja 2.
  }
}
