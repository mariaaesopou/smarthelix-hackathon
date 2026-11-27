# smarthelix-hackathon

## Project purpose

SmartHelix Hackathon, Project 2: an aggregator for SMEs, young entrepreneurs and
freelancers, with Spark ML recommendations.

**Status: Day 2.** The database, shared schemas and a runnable stack are in place.
The API serves only `/health`; the worker, web app and mock sources are placeholders.

## Architecture

React, Fastify, PostgreSQL, Redis + BullMQ and PySpark. Spark never runs in the
request path.

- [Architecture, rules and schedule](docs/architecture.md)
- [ER diagram](docs/er-diagram.md)

## Repository layout

| Folder | Contents |
|---|---|
| `apps/web`, `apps/api`, `apps/worker` | React front-end; Fastify API; queue worker |
| `services/pipeline` | Python: connectors, ETL, resolution, Spark job runner |
| `services/ml` | PySpark ML functions: preprocessing, similarity, matchmaking, clustering, benchmark |
| `services/mock-sources` | Mock external sources |
| `packages/shared` | JSON Schemas, examples, generated types, constants |
| `db` | `migrations`, `seeds`, `tests` |
| `benchmarks` | `generate`, `ground_truth`, `run`, `results` |
| `data` | Local data, git-ignored |
| `docs` | Architecture, ER diagram, `report`, `slides` |
| `.github/workflows` | CI, not set up yet |

## Prerequisites

- Docker with Compose, to run the stack.
- Node 22+ and pnpm (`npm install -g pnpm@12.23.0`), to develop.

## Setup

```bash
cp .env.example .env
docker compose up --build
```

Defaults work as they are; edit `.env` only to change them.

Services start in order once their dependencies are healthy, and restart if they
crash. The web app reloads when you save a file in `apps/web/src`; for other
changes, run `docker compose up --build` again.

| Service | Address |
|---|---|
| Web | http://localhost:5173 |
| API | http://localhost:3000/health |
| Mock sources | http://localhost:4000/health |
| PostgreSQL / Redis | localhost:5432 / localhost:6379 |

## Running

```bash
pnpm install
pnpm dev          # same as docker compose up --build
pnpm db:migrate   # apply new migrations
pnpm generate     # after editing packages/shared/schemas; commit the result
```

Never edit an applied migration; add a new file in `db/migrations`.
Never edit files in a `generated` folder.

## Tests

```bash
pnpm db:test      # schema and search checks; needs the stack running
pnpm test         # schemas against their examples
pnpm typecheck
```

API, worker and pipeline tests: TBD.

## Data and seeds

```bash
pnpm db:seed      # synthetic data; needs the stack running
pnpm etl:a --mode full   # import source A through its connector
```

Connectors and how a run works: [services/pipeline/README.md](services/pipeline/README.md).

`db:seed` loads `db/seeds/001_dev.sql` (4 hand-written profiles with ML results)
and `db/seeds/002_profiles.sql` (2,000 generated profiles), then
`db/seeds/003_dev_partners.sql` (hand-made partners until the Spark matchmaking
job exists). All are safe to run
again. To regenerate the 2,000 profiles and the mock-source data:

```bash
python benchmarks/generate/generate_seed_profiles.py
```

The sources themselves come from a migration, so a database without seeds still
has `source_a` and `source_b`. Files in `data/` are git-ignored.

## Benchmark

Exact search vs LSH in Spark on over 1M vectors; plan in
[architecture.md](docs/architecture.md#benchmark). Commands and results: TBD.

## Team and roles

TBD.

## Contributing

- `main` is protected: work on a branch and open a pull request with 1 approval.
- Name branches by type, for example `feat/search-page` or `chore/day1-repo`.
- Force pushes to `main` and deleting it are blocked. CI checks: TBD.
