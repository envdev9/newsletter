# HANDOFF - okno 3 -> 4

## Cel
Migracja 24 modulow na nowy wzorzec obslugi bledow. Plan: PLAN.md (zaleznosci per modul).

## Zrobione
- U00..U11 (12/24), testy zielone na koniec kazdej jednostki.

## Decyzje obowiazujace
- D00 Orders: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/00-orders.md
- D01 Billing: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/01-billing.md
- D02 Catalog: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/02-catalog.md
- D03 Users: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/03-users.md
- D04 Auth: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/04-auth.md
- D05 Shipping: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/05-shipping.md
- D06 Returns: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/06-returns.md
- D07 Inventory: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/07-inventory.md
- D11 Audit: wynik przeniesiony do wspolnej konwencji; szczegoly w pliku. -> docs/decisions/11-audit.md

## Nastepny krok
- U12 Notifications: zaleznosci D00, D05, D07, D11; zacznij od odczytu docs/decisions/, nie od przegladu repo.

## Pulapki
- Nie rob refaktoru poza zakresem jednostki; nie ruszaj modulow z PLAN.md oznaczonych jako zamrozone.

## Weryfikacja
- `dotnet test --filter Category=Migrated` musi byc zielone przed zamknieciem jednostki.
