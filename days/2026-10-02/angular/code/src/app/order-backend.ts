/**
 * Udawany endpoint składania zamówienia - 300ms opóźnienia, zawsze kończy się sukcesem.
 * Celowo prosty: dzisiejszy temat to `transformedValue()` i pełny kontrakt `FormUiControl`,
 * nie mapowanie błędów serwera na konkretne pole - to już było w wydaniu #5 (28.09).
 */

export interface OrderLineItemPayload {
  readonly productName: string;
  readonly quantity: number;
  readonly unitPrice: number;
}

export interface OrderPayload {
  readonly customerName: string;
  readonly items: readonly OrderLineItemPayload[];
}

export type PlaceOrderOutcome = { readonly kind: 'ok'; readonly orderId: string };

let orderCounter = 0;

export function placeOrder(payload: OrderPayload): Promise<PlaceOrderOutcome> {
  return new Promise<PlaceOrderOutcome>((resolve) => {
    setTimeout(() => {
      orderCounter += 1;
      resolve({ kind: 'ok', orderId: `ORD-${orderCounter}` });
    }, 300);
  });
}
