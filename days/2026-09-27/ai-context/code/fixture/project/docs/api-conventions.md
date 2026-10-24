# API conventions

## Status codes
- 201 with a `Location` header for creation. 200 for queries. 204 for successful deletes.
- 400 only for malformed requests; validation failures are 422 with ProblemDetails.
- 404 when the resource does not exist for the caller; never 403 to hide existence.
- 409 for optimistic concurrency conflicts (`If-Match` mismatch).

## Error format
Always RFC 9457 ProblemDetails. `type` is a stable URI under `https://errors.contoso.example/`,
`title` is short and not localized, `detail` is for humans, `traceId` is always present.

## Pagination
Cursor-based: `?limit=50&cursor=...`. Response has `items` and `nextCursor` (null at the
end). Limit is capped at 200. No total counts on large collections.

## Versioning
Version in the path (`/v1/...`). A new version is created only for breaking changes.
Adding optional fields to responses is not breaking.

## Naming
Plural nouns for collections, kebab-case for multiword segments, camelCase in JSON.
