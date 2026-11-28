# services/ml (Role 2)

PySpark ML functions. Each is `DataFrame in -> DataFrame out`; Role 1's Spark runner
loads `profiles`, calls them and writes the ML tables.

| Function | Status | Output |
| --- | --- | --- |
| `to_profile_frame(df)` | done | the contract columns of `profiles`, NULLs -> empty |
| `preprocess(df)` | done | adds `tokens` |
| `build_features(df)` | done | adds `features` (L2-normalised TF-IDF) and returns the fitted model |
| `compute_similar(df)` | done | `similar_profiles`: `profile_id, similar_id, rank, score` (top 20 stored, API shows 10) |
| `compute_partners(df)` | done | `potential_partners`: `profile_id, partner_id, rank, score, reasons` (top 20) |
| `compute_clusters(df)` | day 6-7 | `cluster_assignments`: `profile_id, cluster_id, label` |

`run_id` is added by the runner when it writes. Names and ground-truth labels are never features.

## Preprocessing

description + services + skills -> lowercase -> Greek accents stripped (ς -> σ) ->
split on non-letters -> tokens under 2 characters and digit-only tokens dropped ->
the profile's own name tokens dropped -> English (Spark) and Greek stopwords removed.
Built-in Spark functions only, no Python UDFs.

## Features

`tokens` -> CountVectorizer (min_df=4) -> IDF -> Normalizer (L2). Every vector has
length 1, so the dot product of two vectors is their cosine similarity.

- CountVectorizer rather than HashingTF: the vocabulary maps each position back to its
  word (`vocabulary(model)`), which cluster labels and match reasons need.
- min_df=4: on the 2k seed every word in 1-3 profiles is a typo and every real word is
  in 6 or more (376 words kept). A word in every profile gets IDF 0.
- A vocabulary that comes out empty (too few profiles) raises a clear `ValueError`.

## Similar profiles

`compute_similar(profiles, k=20)` runs preprocess -> features -> top k. Cosine is the dot
product of the unit vectors, computed as a sparse join on shared words (exact, built-in
Spark only; pairs with no shared word are never generated). Ties are broken by
`similar_id`. The plan's top 10 is what the API shows; 20 are stored so the API can drop
merged or deleted profiles (docs/architecture.md, items 15 and 21).

Hand check on the 2k seed (`python -m smarthelix_ml`): 5 profiles from 5 sectors all get
neighbours from their own field; about 4 s for all 2,004 profiles. Known limit: TF-IDF
matches identical words only, so Greek-only and English-only profiles almost never match
each other; bilingual profiles are the bridge (multilingual embeddings are CUT-2).

## Potential partners

`compute_partners(profiles, k=20)`: who offers what a profile needs. Whole phrases are the
terms ("website maintenance" is one term), normalised like the tokens, and only phrases
offered by at least 4 profiles count (on the 2k seed typo phrases are offered by at most 3,
real ones by 10 or more).

```
idf(p) = log((n + 1) / (df(p) + 1))            df = profiles offering p
w_A(p) = idf(p) / ||idf over A's needs||       w_B(p) = idf(p) / ||idf over B's offers||
base   = sum over p in needs(A) and offers(B) of w_A(p) * w_B(p)       (cosine, 0..1)
score  = base + 0.05 * [same region] + 0.05 * [different profile type]
```

B is a candidate only if it covers at least one of A's needs; `reasons` is the JSON text
`{"matched_needs": [...]}` with those needs in A's own wording (the runner writes it to the
jsonb column). Chosen by measurement on the 2k seed, labels used for inspection only: share
of top-10 partners from an archetype A really needs is 95.8% for cosine, 93.9% for the SQL
rule in `db/seeds/003_dev_partners.sql`, 92.7% for idf-weighted coverage. Cosine favours
focused providers (5.8 offers on average) over padded lists (8.5). The 0.05 boosts raise
same-region partners in the top 10 from 14% to 34% and different-type from 62% to 84%,
at 94.4%. Known limits: a need with a typo never matches (19 of 1,806 profiles get no
partner for that reason), and needs and offers in different languages do not match.

## Run

Python 3.11 and Java 17. From the repo root, with the stack up and seeds loaded:

```bash
pnpm db:seed                          # 4 dev + 2,000 generated profiles
cd services/ml
python -m pytest                      # unit tests, no database needed
cd src && python -m smarthelix_ml     # load profiles over JDBC, print token and feature stats
```

Database: `ML_DATABASE_URL` (postgres://...), default is the local compose database.
On Windows, Git Bash rewrites `/seeds/...`: prefix `pnpm db:seed` with `MSYS_NO_PATHCONV=1`.
PySpark 3.5 needs numpy < 2, and `vector_to_array` imports pandas, which must then be < 3 (both pinned in pyproject.toml).
Windows without `winutils.exe`: reading and computing work (the JDBC jar goes on the
driver classpath); writing Parquet for the benchmark will need winutils or Docker.
