import { max, min, required, schema } from '@angular/forms/signals';

/** Jedna pozycja zamówienia - dokładnie to, co w .NET byłoby rekordem `record LineItem(...)`. */
export interface LineItem {
  productName: string;
  quantity: number;
}

/**
 * Reguły walidacji JEDNEJ pozycji zamówienia, wydzielone jako osobny, nazwany `schema<T>(...)`
 * - a nie funkcja anonimowa wklejona inline do `form()`. Dzięki temu można ją zastosować do
 * KAŻDEGO elementu tablicy przez `applyEach()` (sekcja 1 artykułu) - odpowiednik
 * `AbstractValidator<LineItem>` z FluentValidation, użytego przez `RuleForEach()` w .NET,
 * tylko że tu ten sam obiekt schematu da się też wpiąć osobno przez `apply()` gdziekolwiek
 * indziej w drzewie formularza (np. do pojedynczego, niezagnieżdżonego pola tego typu).
 */
export const lineItemSchema = schema<LineItem>((item) => {
  required(item.productName, { message: 'Nazwa produktu jest wymagana' });
  min(item.quantity, 1, { message: 'Ilość musi być co najmniej 1' });
  max(item.quantity, 99, { message: 'Ilość nie może przekraczać 99' });
});
