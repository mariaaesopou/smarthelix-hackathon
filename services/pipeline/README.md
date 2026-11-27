# services/pipeline

Python: connectors, ETL, resolution and the Spark job runner. Every job runs as
`python -m pipeline <job>` (`cli.py`); the worker starts jobs the same way.

## Run

No local Python needed; both commands run in a container (the stack must be up):

```bash
pnpm etl:a --mode full           # import every profile of source A
pnpm etl:a --mode incremental    # only profiles changed since the last run
pnpm test:pipeline               # unit tests and database tests
```

Output: the run id and counts (`fetched`, `inserted`, `updated`, `unchanged`,
`invalid`, `blocked`, `profiles_created`, `profiles_updated`). Exit codes: 0
success, 75 retry later (source down, another run active), 65 permanent failure
(`errors.py`). Inside the worker image the same run is
`python -m pipeline etl --source source_a --mode full`.

## How one run works (ETL)

1. **Extract:** the connector reads the source page by page (`pages`). An
   incremental run passes the last successful watermark minus 5 minutes.
2. **Transform:** each raw record is validated against the source schema
   (`source-a-record.json`), mapped to `NormalizedRecord` and cleaned
   (`etl/clean.py`): trimmed text, no duplicate list items, canonical region
   names, http(s) links only. A record that fails is counted as `invalid` and
   skipped; its field names are reported, never its values.
3. **Load:** upsert into `source_records` on `(source, source_id)`, storing only
   the normalised fields in `raw`. Each page and the run's cursor are committed
   together. Erased records (blocklist in `erasures`) are skipped.
4. **Resolve:** every record whose hash changed creates or updates its profile,
   one record to one profile for now, and `data_version` goes up.

Every run is a `sync_runs` row: `etl_running` → `etl_done` → `resolved`, or
`failed` with the error type. The watermark only moves when a run succeeds.

## Add a source

Write `connectors/source_x.py` with a `pages(since)` that yields `Page`s and a
`map(raw)` that returns a `NormalizedRecord`, using the helpers in
`etl/clean.py`, then register it in `jobs/etl.py`. Loading, resolution and
`sync_runs` need no change.

## Tests

`tests/test_source_a.py` checks mapping and cleaning, including every record of
the source A mock. `tests/test_etl_db.py` runs the ETL against the database
inside a transaction that is rolled back. When the database is not reachable it
fails rather than skips; `SKIP_DB_TESTS=1` skips it on purpose.
