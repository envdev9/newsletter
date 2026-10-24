# SNAPSHOT t=300 (zlozony z 300 zdarzen; pelna historia: docs/log/events.log)

## Wartosci
- conv/async = usun ValueTask w audit
- conv/errors = wydziel ValueTask w search
- conv/logging = wydziel rekordy w reports
- conv/naming = zachowaj outbox w search
- conv/nullability = uzyj Span<byte> w search
- decision/audit = uzyj Result<T> w audit
- decision/billing = zachowaj IOptions<T> w pricing
- decision/catalog = uzyj Span<byte> w billing
- decision/gateway = uzyj Polly retry w payments
- decision/identity = usun init-only w pricing
- decision/inventory = uzyj ILogger<T> w billing
- decision/notifications = usun ILogger<T> w billing
- decision/orders = zachowaj ValueTask w identity
- decision/payments = uzyj init-only w orders
- decision/pricing = przenies Span<byte> w pricing
- decision/reports = zachowaj outbox w payments
- decision/search = przenies outbox w orders
- decision/shipping = zamien ILogger<T> w notifications
- tmp/16 = sprawdzam Result<T>
- tmp/17 = sprawdzam outbox

## Zbiory
- pitfall: nie przenies ILogger<T> (zgodnie z konwencja z jednostki 0) | nie przenies Result<T> (unikamy zmiany schematu bazy) | nie przenies init-only (wymog z przegladu bezpieczenstwa) | nie przenies rekordy (uproszcza testy jednostkowe) | nie usun CancellationToken (zespol platformy wymaga tego formatu) | nie usun CancellationToken (zgodnie z konwencja z jednostki 0) | nie usun DateTimeOffset (bo poprzednie podejscie lamalo kontrakt API) | nie usun wyjatek domenowy (zespol platformy wymaga tego formatu) | nie uzyj DateTimeOffset (zgodnie z konwencja z jednostki 0) | nie uzyj IOptions<T> (po awarii na srodowisku testowym) | nie uzyj IOptions<T> (zgodnie z konwencja z jednostki 0) | nie uzyj Polly retry (wymog z przegladu bezpieczenstwa) | nie uzyj ValueTask (uproszcza testy jednostkowe) | nie uzyj outbox (mniej alokacji na goracej sciezce) | nie wydziel CancellationToken (bo poprzednie podejscie lamalo kontrakt API) | nie wydziel DateTimeOffset (bo poprzednie podejscie lamalo kontrakt API) | nie zachowaj rekordy (bo poprzednie podejscie lamalo kontrakt API) | nie zamien CancellationToken (wymog z przegladu bezpieczenstwa)
- todo: przenies DateTimeOffset | przenies Span<byte> | zachowaj wyjatek domenowy | usun Polly retry

## Liczniki
- done = 41
