import { max, min, required, schema } from '@angular/forms/signals';

/** Jedna pozycja zamówienia: produkt, ilość (stepper), cena jednostkowa (tekst z przecinkiem). */
export interface LineItem {
  productName: string;
  quantity: number;
  unitPrice: number;
}

export function emptyLineItem(): LineItem {
  return { productName: '', quantity: 1, unitPrice: 0 };
}

/**
 * Reguły walidacji JEDNEJ pozycji zamówienia - reużywalna `schema<T>()` nałożona na całą
 * tablicę przez `applyEach()` (wydanie #7, 30.09). `min(unitPrice, 0.01)` to walidator NA
 * POZIOMIE SCHEMATU, niezależny od błędów PARSOWANIA zgłaszanych przez `PriceInput`
 * (`price-input.ts`) - oba rodzaje błędów trafiają do tego samego `errors()` pola i renderują
 * się razem (patrz artykuł, sekcja 1).
 */
export const lineItemSchema = schema<LineItem>((item) => {
  required(item.productName, { message: 'Nazwa produktu jest wymagana' });
  min(item.quantity, 1, { message: 'Ilość musi być co najmniej 1' });
  max(item.quantity, 99, { message: 'Ilość nie może przekraczać 99' });
  min(item.unitPrice, 0.01, { message: 'Cena musi być większa od zera' });
});
