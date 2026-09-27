# Architecture

## Layering
Orders.Api depends on Orders.Domain and Orders.Infrastructure. Orders.Domain depends on
nothing. Orders.Infrastructure depends on Orders.Domain only. The direction of
dependencies is enforced by an architecture test in `Orders.Domain.Tests`.

## Modules
- Ordering: create, cancel, ship. Aggregate root is `Order`; lines are value objects.
- Pricing: price lists, discounts. Called from Ordering through `IPricingService`.
- Notifications: outbox pattern; a background service publishes integration events.

## Persistence
EF Core with one `DbContext` per module. No cross-module joins; use IDs and read models.
Migrations live in `Orders.Infrastructure/Migrations`. The outbox table is shared.

## Cross-cutting
- Logging: Serilog, structured, no PII in messages.
- Time: inject `TimeProvider`; never call `DateTime.UtcNow` in domain code.
- Errors: domain returns `Result<T>`; exceptions are for programmer errors only.

## Why not a shared kernel library
Two earlier attempts leaked infrastructure types into the domain. The rule is: if a type
needs a NuGet package other than the BCL, it does not belong in Orders.Domain.
