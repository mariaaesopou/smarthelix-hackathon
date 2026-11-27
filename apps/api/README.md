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
| `GET /profiles/{id}/similar` | `Recommendation[]` (`recommendation.json`) | 307, 400, 404 |
| `GET /profiles/{id}/partners` | `Recommendation[]` (`recommendation.json`) | 307, 400, 404 |

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

### `GET /profiles/{id}/similar` and `/partners`

Recommendations the Spark jobs wrote, read from the run in `ml_current`
(`similarity` → `similar_profiles`, `matching` → `potential_partners`). The API
never computes them, and a half-written run is never visible.

- **200:** a list of `{ profile: ProfileCard, rank, score, matched_needs }`, best
  first. `matched_needs` lists the needs of the requested profile that a partner
  offers; it is empty for similar profiles. No current run, or no rows, gives `[]`.
- `limit`: 1–20, default 10 (the jobs store 20 per profile).
- A target that was merged is replaced by its survivor; deleted targets and the
  profile itself are dropped; each profile appears once, at its best rank, and
  ranks restart at 1 (architecture rule 21).
- **307** for a merged id (`Location: ../{survivor}/similar`), **404** for an
  unknown or deleted one, **400** for a malformed id or limit.

Until the Spark matchmaking job exists, `pnpm db:seed` loads hand-made partners
(`db/seeds/003_dev_partners.sql`: a partner offers something the profile needs).
Real similar profiles come from `docker compose --profile tools run --rm pipeline
python -m pipeline similarity`.

## Data source

`PROFILES_SOURCE` (in `.env`) chooses where profiles come from:

- `database` (default): PostgreSQL, with the search in `db/migrations/*_search_functions.sql`.
- `fixtures`: the four profiles and their hand-made similar profiles and partners in
  `src/repositories/fixtures/profiles.json`, no database needed.

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
