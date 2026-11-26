# services/ml (Role 2)

PySpark ML functions. Each is `DataFrame in -> DataFrame out`; Role 1's Spark runner
loads `profiles`, calls them and writes the ML tables.

| Function | Status | Output |
| --- | --- | --- |
| `to_profile_frame(df)` | done | the contract columns of `profiles`, NULLs -> empty |
| `preprocess(df)` | done | adds `tokens` |
| TF-IDF features | day 3-4 | |
| `compute_similar(df)` | day 4-5 | `similar_profiles`: `profile_id, similar_id, rank, score` (top 20 stored, API shows 10) |
| `compute_partners(df)` | day 5-6 | `potential_partners`: `profile_id, partner_id, rank, score, reasons` |
| `compute_clusters(df)` | day 6-7 | `cluster_assignments`: `profile_id, cluster_id, label` |

`run_id` is added by the runner when it writes. Names and ground-truth labels are never features.

## Preprocessing

description + services + skills -> lowercase -> Greek accents stripped (ς -> σ) ->
split on non-letters -> tokens under 2 characters and digit-only tokens dropped ->
the profile's own name tokens dropped -> English (Spark) and Greek stopwords removed.
Built-in Spark functions only, no Python UDFs.

## Run

Python 3.11 and Java 17. From the repo root, with the stack up and seeds loaded:

```bash
docker compose exec -T postgres bash /dbtests/run.sh /seeds/002_profiles.sql   # 2k profiles
cd services/ml
python -m pytest                      # unit tests, no database needed
cd src && python -m smarthelix_ml     # load profiles over JDBC and print token stats
```

Database: `ML_DATABASE_URL` (postgres://...), default is the local compose database.
On Windows, Git Bash rewrites `/seeds/...`: prefix the first command with `MSYS_NO_PATHCONV=1`.
Windows without `winutils.exe`: reading and computing work (the JDBC jar goes on the
driver classpath); writing Parquet for the benchmark will need winutils or Docker.
