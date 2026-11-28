# services/pipeline

Python: connectors, ETL, resolution and the Spark job runner. Every job runs as
`python -m pipeline <job>` (`cli.py`); the worker starts jobs the same way.

## Run

No local Python needed; these commands run in a container (the stack must be up):

```bash
pnpm etl:a --mode full           # import every profile of source A
pnpm etl:a --mode incremental    # only profiles changed since the last run
pnpm etl:b --mode full           # import source B's freelancer export
pnpm test:pipeline               # unit tests and database tests
```

Through the API, `POST /sync/source_a` or `POST /sync/source_b` queues the same
run for the worker (see `apps/api/README.md`).

Output: the run id and counts (`fetched`, `inserted`, `updated`, `unchanged`,
`invalid`, `blocked`, `profiles_created`, `profiles_updated`). Exit codes: 0
success, 75 retry later (source down, another run active), 65 permanent failure
(`errors.py`). Inside the worker image the same run is
`python -m pipeline etl --source source_a --mode full`.

## Sources

| | Source A (SMEs, startups) | Source B (freelancers) |
|---|---|---|
| Connector | `connectors/source_a.py` | `connectors/source_b.py` |
| Reads | `GET /a/profiles`, 100 per page | `GET /b/export.json`, the whole export, cut into pages of 100 |
| Schema | `source-a-record.json` | `source-b-record.json` |
| Type | `SME` → `sme`, `Startup` → `young_entrepreneur` | always `freelancer` |
| Partial sync | `updated_since` = last watermark − 5 min, plus the hash | the hash only: B has no `updated_since`, so every run reads the export and unchanged records are counted `unchanged` |
| Not stored | — | `hourlyRate`, `availability` (validated, never mapped) |

## How one run works (ETL)

1. **Extract:** the connector reads the source page by page (`pages`).
2. **Transform:** each raw record is validated against its source schema, mapped
   to `NormalizedRecord` and cleaned (`etl/clean.py`): trimmed text, no
   duplicate list items, canonical region names, http(s) links only. A record
   that fails is counted as `invalid` and skipped; its field names are reported,
   never its values.
3. **Load:** upsert into `source_records` on `(source, source_id)`, storing only
   the normalised fields in `raw`. A record whose hash did not change is
   `unchanged`. Each page and the run's cursor are committed together. Erased
   records (blocklist in `erasures`) are skipped.
4. **Resolve:** every record whose hash changed creates or updates its profile,
   one record to one profile for now, and `data_version` goes up.

Every run is a `sync_runs` row: `etl_running` → `etl_done` → `resolved`, or
`failed` with the error type. A run started by `POST /sync` continues the row
the API created (`--sync-run-id`). The watermark only moves when a run succeeds.

## Add a source

Write `connectors/source_x.py` with a `pages(since)` that yields `Page`s and a
`map(raw)` that returns a `NormalizedRecord`, using the helpers in
`etl/clean.py`. Register it in `jobs/etl.py` and add it to `syncSources` in
`packages/shared/constants.json` so `POST /sync` accepts it. Loading,
resolution and `sync_runs` need no change.

## Tests

`tests/test_source_a.py` and `tests/test_source_b.py` check mapping and
cleaning, including every record of each mock source and that source B's private
fields are never kept. `tests/test_etl_db.py` runs the ETL against the database
inside a transaction that is rolled back. When the database is not reachable it
fails rather than skips; `SKIP_DB_TESTS=1` skips it on purpose.
