# smarthelix-hackathon

SmartHelix Hackathon, Project 2: an aggregator for SMEs, young entrepreneurs and
freelancers, with Spark ML recommendations.

**Status: Day 2.** The database, shared schemas and a runnable stack are in place.
The API serves only `/health`; the worker, web app and mock sources are placeholders.

## Run

Needs Docker with Compose.

```bash
docker compose up --build
```

| Service | Address |
|---|---|
| Web | http://localhost:5173 |
| API | http://localhost:3000/health |
| Mock sources | http://localhost:4000/health |
| PostgreSQL / Redis | localhost:5432 / localhost:6379 |

Defaults work as they are; copy `.env.example` to `.env` to change them.

## Develop

Needs Node 22+ and pnpm (`npm install -g pnpm@12.23.0`).

```bash
pnpm install
pnpm db:seed      # synthetic data; needs the stack running
pnpm db:test      # schema and search checks
pnpm test         # schemas against their examples
pnpm typecheck
pnpm generate     # after editing packages/shared/schemas; commit the result
```

Never edit an applied migration; add a new file in `db/migrations`.
Never edit files in a `generated` folder.

## Documentation

- [Architecture, rules and schedule](docs/architecture.md)
- [ER diagram](docs/er-diagram.md)
