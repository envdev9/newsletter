# Orders.Api - local rules

- Endpoints are static classes with a `Map(IEndpointRouteBuilder)` method, one per file.
- Every request DTO has a FluentValidation validator in `Validators/`; register via assembly scan.
- Do not inject `DbContext` into endpoints; go through the module service.
