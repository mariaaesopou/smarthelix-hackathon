# Architecture

**[MUST Dn]** is due by day n. Cut order when short of time: **[CUT-1]** match
review flow, **[CUT-2]** embeddings, **[CUT-3]** full erasure procedure.
**Unverified** marks behaviour to test before relying on it.

## Overview

```
React ─▶ Fastify API ─────────────▶ PostgreSQL 17 ◀── migrate (one-shot)
             │ sync_runs row + job          ▲
             ▼                              │
           Redis ─▶ Node worker (1 replica) │
  queue etl          ├─ etl(source) ────────┤ Python ◀─ sources A, B
   (parallel)        │     ▼ on success     │
  queue resolution   ├─ resolution ─────────┤ Python: dedup, build profiles,
   (concurrency 1)   │     ▼ dirty          │         data_version + 1
  sweep (30 s)       ├─ debounce            │
                     │     ▼                │
  queue ml           └─ ml ─────────────────┘ spark-submit
   (concurrency 1)

Separate: Parquet ─▶ exact vs LSH in Spark ─▶ charts
```

`migrate` applies the migrations and exits; `api` and `worker` wait for it to
succeed. Order is always etl(source) → resolution → ml. Resolution is its own job
so it can retry without fetching again. Spark never runs in the request path.

| Folder | Contents |
|---|---|
| `apps/web`, `apps/api`, `apps/worker` | React; Fastify; BullMQ consumers, sweep, process launcher |
| `services/pipeline` | Python: connectors, etl, resolution, erasure, and spark_jobs (the runner that loads data, calls `services/ml` and writes the ML tables) |
| `services/ml` | PySpark ML functions (preprocessing, similarity, matchmaking, clustering), evaluation and the LSH benchmark code |
| `services/mock-sources` | Mock source A API and source B export |
| `packages/shared` | JSON Schemas (source of truth), examples, generated types, constants |
| `db` | Migrations, seeds, schema tests |
| `benchmarks`, `data` | LSH experiment; git-ignored Parquet |

The data model is in [er-diagram.md](er-diagram.md).

## Advisory locks

Keys are in `packages/shared/constants.json`.

| Key | ETL page commit | Resolution | ML run | Erasure |
|---|---|---|---|---|
| `K_ERASURE` | shared, transaction | shared, transaction | shared, session | **exclusive** |
| `K_ML` | – | – | **exclusive**, session | – |

- Take `K_ERASURE` before `K_ML`, always, to avoid deadlock.
- The Spark driver process holds both ML locks on one dedicated connection for the
  whole run. It uses `pg_try_advisory_lock` for `K_ML` and exits 75 if it is taken.
- ETL and resolution never take `K_ML`, so they can run during an ML run.
- Erasure waits for a running ML run, so pause the queues first.

## Rules

### Sync and deletion
1. **[MUST D4]** Commit each page and its cursor in one transaction. Advance the
   watermark only on success; the next run overlaps slightly.
2. **[MUST D4]** Store only allowlisted fields in `raw`.
3. **[MUST D7]** Soft-delete only after a complete, successful full sync. Abort if
   more than 20% vanished (configurable).

### Resolution
4. **[MUST D4]** Process records whose `resolved_hash` differs from `hash`, or whose
   deletion state changed (set `resolved_hash` to NULL then). Start one-to-one.
5. **[MUST D7]** Auto-merge on same type + normalised name + own website domain,
   ignoring shared domains such as facebook.com.
6. **[MUST D7]** Flatten `merged_into` on every merge: it points at the survivor.
7. **[CUT-1]** Name + region or high similarity only creates a `match_candidates`
   row for review. If cut, those profiles stay separate.

### Jobs
8. **[MUST D6]** Insert `sync_runs`, then add the job with that UUID as `jobId`.
   BullMQ 6.7.10 rejects ids that are integers or contain `:`.
9. **[MUST D6]** On ETL success set `etl_done` and enqueue resolution. The sweep
   repairs a missing job at either step, removing retained failed jobs first.
10. **[MUST D6]** Resolution bumps `data_version` in its own transaction, only if
    something changed.
11. **[MUST D6]** ML debounce: a kind is dirty when its current run's `data_version`
    is below `pipeline_state.data_version`. The sweep creates one `ml_batches` row
    when no etl, resolution or ml work is active and the last change is 60 s old.
    After 10 minutes dirty it stops waiting for quiet or ETL, but still waits for
    resolution and ML. At most 3 attempts per `data_version`. Database state
    survives Redis loss and catches changes made during a run.
12. **[MUST D5]** Launch processes with asynchronous `spawn`. Exit codes: 0 success,
    75 retryable, 65 permanent.
13. **[MUST D5]** ML queue: one replica, `lockDuration` 120 s, `stalledInterval`
    60 s, `maxStalledCount` 1. **Unverified:** test by killing the worker.
14. **[MUST D5]** A timeout or lost lock kills the process tree. Cap Spark memory.
    Pin one BullMQ version. **Unverified:** its minimum Redis version.

### Machine learning
15. **[MUST D5]** Similarity job: TF-IDF + cosine, top 20 per profile.
16. **[MUST D6]** Clustering job (KMeans, labels from top words) and matchmaking job
    (needs → offers) with the scoring formula documented.
17. **[MUST D6]** One current run per kind, so a clustering failure cannot block the
    others. Write under a new `run_id`, validate, then switch that kind's pointer in
    one transaction. Retry only failed kinds.
18. **[MUST D6]** Write through JDBC. **Unverified:** UUID and JSONB columns; if they
    fail, write plain types to staging and cast in SQL.
19. **[MUST D7]** Evaluate: precision@k, matching hit rate, silhouette + NMI/ARI,
    with noisy text, random and same-sector baselines, and a small human-rated
    sample. Labels are never model features.
20. **[CUT-2]** BGE-M3 embeddings in Parquet. TF-IDF stays the core method.

### API
21. **[MUST D5]** Replace merged ML targets with the survivor, drop deleted targets
    and the profile itself, deduplicate by best rank. Store 20, return 10.
22. **[MUST D5]** `/profiles/:id`, `/similar` and `/partners` return 307 for a merged
    id (not 308: merges can be undone). Deleted or erased ids return 404.
23. **[MUST D4]** Capped OFFSET pagination.

### Search (tested on PostgreSQL 17.12)
24. **[MUST D2]** `unaccent` is STABLE, so `f_unaccent` wraps it as IMMUTABLE. It
    removes tonos and dialytika. The `greek` config exists but has no stop words, so
    `f_tsq` carries a list. The column is:

```sql
search tsvector NOT NULL GENERATED ALWAYS AS (
     setweight(public.f_tsv(name), 'A')
  || setweight(public.f_tsv(public.f_arr(skills)), 'B')
  || setweight(public.f_tsv(public.f_arr(services)), 'B')
  || setweight(public.f_tsv(description), 'C')
) STORED
```

   - Match: `search @@ f_tsq(:q) OR f_norm(:q) <% f_norm(name)`.
   - Rank: `0.7 * coalesce(ts_rank_cd(search, f_tsq(:q), 1|32), 0) + 0.3 *
     word_similarity(f_norm(:q), f_norm(name))`, then `id`. Tune on about 20 queries.
   - `f_tsq` ORs greek, english and simple per token and ANDs the tokens. Combining
     three whole queries misses mixed-language searches.
   - Without Greek support, fall back to `simple` + trigram and an accent
     `translate()`. `db/tests/schema.sql` checks the configs exist.

### Benchmark
25. **[MUST D7]** Parquet only: structured, L2-normalised vectors, held-out queries,
    cached and warmed up. Over 1M vectors. **Unverified:** runtime at that size.
26. **[MUST D7]** Primary: one batch (start with 200 queries), `approxSimilarityJoin`
    vs a batched exact join, same top-k step and same engine. Report batch time ÷
    queries (median of at least 5 runs) and Recall@10. The join takes a distance
    threshold: set it from calibration queries and report its recall loss separately.
27. **[MUST D7]** Secondary: p50/p95 of single `approxNearestNeighbors` calls,
    labelled as including job overhead. Report index build time separately. Chart
    recall and time against `numHashTables` and `bucketLength`.

### Privacy and erasure
28. **[MUST D4]** Connectors check the blocklist (`erasures.key_hmac`) inside the
    insert transaction, before storing. The key is an HMAC of an unambiguous encoding
    of (source, source_id); losing the secret breaks the blocklist.
29. **[MUST D4]** Logs and job payloads hold internal UUIDs only. Partner `reasons`
    and cluster labels never contain names.
30. **[MUST D7]** Deletion script, after a person confirms the scope: insert the
    HMACs, take `K_ERASURE` exclusively, then in one transaction delete from all ML
    tables in every run (as subject or target), `match_candidates`,
    `profile_sources`, `source_records` and `profiles`, merged ones first. Rebuild
    any surviving profile and bump `data_version`.
31. **[CUT-3]** Automated full procedure. If cut, it stays this manual checklist:
    - [ ] pause queues before the script, resume after
    - [ ] delete `data/app/` snapshots, saved models and embeddings
    - [ ] remove affected evaluation rows
    - [ ] remove affected Redis jobs, including failure text
    - [ ] clear or redact application and container logs
    - [ ] expire backups; reapply `erasures` after any restore
    - [ ] `VACUUM` affected tables, verify no copies remain, mark completed

Someone qualified should review the legal side, including keeping the HMAC.

## Schedule

| Day | Back-end and infra | Other roles **[MUST]** |
|---|---|---|
| 1 | Folders, `.env.example`, README, protected `main` | Agree schemas |
| 2 | Compose, migrations, schemas, ER diagram | |
| 3 | `/profiles`, `/profiles/{id}` | Synthetic dataset with planted groups |
| 4 | Adapter A, search and filters | React search, results and details on seed data |
| 5 | `/similar`, `/partners`, queues, worker | Similarity job |
| 6 | `/sync`, job chain, sweep, adapter B | Clustering and matching jobs; React on the live API |
| 7 | Partial sync, deletion, dedup, deletion script, OpenAPI | Evaluation and 1M benchmark |
| 8 | Tests and CI | Report draft, screenshots and charts |
| 9 | README, integration fixes | Slides, final report, timed demo rehearsal |

Days 6–7 are the heaviest for back-end. CI tests must cover endpoints, both adapters,
Greek search, merge redirects, retried jobs, two syncs → one ML batch, and an erased
record not being re-imported.
