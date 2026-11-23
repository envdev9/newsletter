---
paths:
  - "src/**/Controllers/**/*.cs"
  - "src/**/Endpoints/**/*.cs"
---

# Controllery / endpointy

<!-- Szablon. Ładuje się przy pracy na plikach z `paths`. Dopasuj ścieżki i uzupełnij <...>. -->

Wzorzec: `src/<...>/Controllers/<X>Controller.cs`

- Controller jest cienki: walidacja wejścia, wywołanie serwisu, mapowanie wyniku na HTTP. Bez logiki biznesowej i bez SQL.
- Wejście i wyjście tylko jako DTO (rekordy) z `<Projekt>.Api/Contracts/`. Encje nie wychodzą poza serwis.
- Każda akcja przyjmuje `CancellationToken` i przekazuje go dalej.
- Kody HTTP: `201` z `Location` dla utworzenia, `204` dla update/delete bez treści, `404` gdy brak zasobu, `400` błędy walidacji, `409` konflikt wersji.
- Autoryzacja: <np. `[Authorize]` na controllerze, polityki `<...>`>. Sprawdzaj własność zasobu w serwisie.
- Walidacja: <np. FluentValidation / DataAnnotations>.
- Routing: <np. `api/v1/[controller]`>, nazwy w liczbie mnogiej.

## Przykład szkieletu

```csharp
[ApiController]
[Route("api/v1/orders")]
public sealed class OrdersController(IOrderService orders) : ControllerBase
{
    [HttpPut("{id:guid}")]
    public async Task<IActionResult> Update(Guid id, UpdateOrderRequest request, CancellationToken ct)
    {
        var result = await orders.UpdateAsync(id, request, ct);
        return result.Match<IActionResult>(_ => NoContent(), error => error.ToProblem());
    }
}
```
