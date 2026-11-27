# API

Fastify (TypeScript). Every response body follows a schema in `packages/shared`.
Through the web app the same routes are under `/api`, for example
`http://localhost:5173/api/profiles`.

## Routes

| Route | Returns | Errors |
|---|---|---|
| `GET /health` | `{ "status": "ok" }` | 503 when the database is down |
| `GET /profiles` | `ProfilePage` (`profile-page.json`) | 400 |
| `GET /profiles/{id}` | `Profile` (`profile.json`) | 307, 400, 404 |

Errors use `error.json`: `{ "statusCode", "error", "message" }`.

### `GET /profiles`

| Parameter | Meaning |
|---|---|
| `q` | Words to find in name, skills, services and description, Greek or English; accents and case are ignored, and similar names match |
| `type` | `sme`, `young_entrepreneur` or `freelancer` |
| `sector`, `region`, `skill`, `source` | Exact value, for example `region=Attica`, `skill=React`, `source=source_b` |
| `page` | From 1, default 1 |
| `per_page` | 1–100, default 20 |

With `q`, results are ranked by relevance; without it, by name. At most 1,000
results can be skipped (`page` × `per_page`); deeper pages return 400. Merged and
deleted profiles are never listed.

### `GET /profiles/{id}`

- **200:** the profile, its sources with links, and its cluster (`null` before the
  first clustering run).
- **307:** the id was merged into another profile; `Location` is the survivor's id,
  relative to `/profiles/`, so it also works behind `/api`.
- **404:** unknown or deleted id. **400:** not a UUID.

## Data source

`PROFILES_SOURCE` (in `.env`) chooses where profiles come from:

- `database` (default): PostgreSQL, with the search in `db/migrations/*_search_functions.sql`.
- `fixtures`: the four profiles in `src/repositories/fixtures/profiles.json`, no database needed.

## Code

`routes` (paths and schemas) → `controllers` (HTTP replies) → `services` (paging
rules) → `repositories` (fixtures or SQL). The SQL is plain and parameterised: the
search uses PostgreSQL functions that an ORM would not express.

## Tests

```bash
pnpm --filter @smarthelix/api test
```

The database tests use the local compose database and roll back everything they
write; they are skipped when it is not running (`TEST_DATABASE_URL` overrides it).
