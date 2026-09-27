# Contoso Orders - project memory

## Build and test
- Build: `dotnet build Orders.sln`
- Test: `dotnet test Orders.sln --no-build`
- Web: `npm ci && npx ng test --watch=false` (in `src/web`)

## Hard rules (things the code cannot tell you)
- Never commit directly to main.
- Do not edit generated files under `Migrations/` by hand; add a new migration instead.
- Money is `decimal` with 2 places; never `double`.

## Read on demand (pointers, NOT imports - no leading at-sign, so not loaded at start)
- Layering, dependency direction, module boundaries: docs/architecture.md
- HTTP status codes, error format, pagination, versioning: docs/api-conventions.md
- Canonical endpoint shape: src/Orders.Api/Endpoints/CreateOrderEndpoint.cs
