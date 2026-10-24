# Contoso Orders - project memory

## General principles
- Write clean code and follow best practices.
- Be careful and think step by step before changing anything.
- Always write high quality, maintainable code.
- Make sure the code is well tested and production ready.

## Repository layout
```
Contoso.Orders/
├── src/
│   ├── Orders.Api/          ASP.NET Core minimal API
│   │   ├── Endpoints/
│   │   ├── Validators/
│   │   └── Program.cs
│   ├── Orders.Domain/       entities, value objects
│   ├── Orders.Infrastructure/  EF Core, repositories
│   └── web/                 Angular client
├── tests/
│   ├── Orders.Api.Tests/
│   └── Orders.Domain.Tests/
├── docs/
└── Orders.sln
```

## Build and test
- Build: `dotnet build Orders.sln`
- Test: `dotnet test Orders.sln --no-build`
- Web: `npm ci && npx ng test --watch=false` (in `src/web`)
- Never commit directly to main.

## Architecture and conventions (always loaded)
@docs/architecture.md
@docs/api-conventions.md

## Example endpoint (copy this shape)
```csharp
public static class CreateOrderEndpoint
{
    public static void Map(IEndpointRouteBuilder app)
    {
        app.MapPost("/orders", async (
            CreateOrderRequest request,
            IValidator<CreateOrderRequest> validator,
            IOrderService orders,
            CancellationToken ct) =>
        {
            var validation = await validator.ValidateAsync(request, ct);
            if (!validation.IsValid)
            {
                return Results.ValidationProblem(validation.ToDictionary());
            }

            var result = await orders.CreateAsync(request.ToCommand(), ct);
            return result.Match(
                order => Results.Created($"/orders/{order.Id}", order.ToDto()),
                error => Results.Problem(error.Message, statusCode: error.StatusCode));
        })
        .WithName("CreateOrder")
        .WithTags("Orders")
        .Produces<OrderDto>(StatusCodes.Status201Created)
        .ProducesValidationProblem();
    }
}
```

## Reminders
- Never commit directly to main.
- Write clean code and follow best practices.
- Do not edit generated files under `Migrations/` by hand; add a new migration instead.
- Money is `decimal` with 2 places; never `double`.
