# Architektura projektu

<!-- Szablon. Bez frontmattera `paths`, więc ładuje się zawsze. Uzupełnij <...>. -->

## Warstwy i odpowiedzialności

| Warstwa | Projekt | Co tam jest | Czego tam nie ma |
|---|---|---|---|
| API | `<Projekt>.Api` | controllery/endpointy, mapowanie DTO, autoryzacja, DI | logika biznesowa, SQL |
| Aplikacja | `<Projekt>.Application` | serwisy, przypadki użycia, interfejsy repozytoriów | HTTP, SQL |
| Domena | `<Projekt>.Domain` | encje, value objects, reguły | zależności od infrastruktury |
| Infrastruktura | `<Projekt>.Infrastructure` | repozytoria Dapper, klienci HTTP | logika biznesowa |

## Przepływ żądania

```
Controller → <X>Service → I<X>Repository → Postgres
          ← DTO (rekord) ← encja/model
```

## Reguły

- Kierunek zależności tylko do środka (Api → Application → Domain). Infrastructure implementuje interfejsy z Application.
- Rejestracja DI: <gdzie, np. `ServiceCollectionExtensions` w każdym projekcie>.
- Błędy biznesowe: <np. `Result<T>` / wyjątki domenowe mapowane na `ProblemDetails` w middleware>.
- <Inne decyzje architektoniczne, np. CQRS, MediatR tak/nie.>
