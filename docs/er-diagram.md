# ER diagram

Column details are in `db/migrations`. `pipeline_state` (one row) and `erasures`
(the blocklist) have no foreign keys.

```mermaid
erDiagram
  sources ||--o{ source_records : lists
  sources ||--o{ sync_runs : "synced by"
  sync_runs |o--o{ source_records : "last seen in"
  source_records ||--o| profile_sources : "belongs via"
  profiles ||--o{ profile_sources : "built from"
  profiles |o--o{ profiles : "merged into"
  source_records ||--o{ match_candidates : proposes
  profiles ||--o{ match_candidates : "candidate for"
  ml_batches ||--o{ ml_runs : contains
  ml_runs ||--o| ml_current : "current for its kind"
  ml_runs ||--o{ similar_profiles : produces
  ml_runs ||--o{ potential_partners : produces
  ml_runs ||--o{ cluster_assignments : produces
  profiles ||--o{ similar_profiles : "subject or target"
  profiles ||--o{ potential_partners : "subject or target"
  profiles ||--o{ cluster_assignments : "assigned in"

  sources {
    text name PK
    text base_url
    text terms_note
  }
  source_records {
    uuid id PK
    text source FK
    text source_id
    jsonb raw
    text hash
    text resolved_hash
    text original_url
    timestamptz source_updated_at
    timestamptz fetched_at
    uuid last_seen_run_id FK
    timestamptz deleted_at
  }
  profiles {
    uuid id PK
    text type "sme, young_entrepreneur, freelancer"
    text name
    text description
    text sector
    text region
    text_array skills
    text_array services
    text_array needs
    text_array languages
    text website
    timestamptz updated_at
    timestamptz deleted_at
    uuid merged_into FK
    tsvector search "generated, for full-text search"
  }
  profile_sources {
    uuid source_record_id PK,FK
    uuid profile_id FK
    text match_method
    real confidence
  }
  match_candidates {
    uuid record_id PK,FK
    uuid profile_id PK,FK
    real score
    text status
  }
  sync_runs {
    uuid id PK
    text source FK
    text mode "full or incremental"
    text status
    text cursor
    timestamptz watermark
    jsonb counts
    text error_code
    timestamptz started_at
    timestamptz finished_at
  }
  ml_batches {
    uuid id PK
    bigint data_version
    text status
    int attempts
  }
  ml_runs {
    uuid id PK
    uuid batch_id FK
    text kind "similarity, matching, clustering"
    bigint data_version
    text status
    jsonb params
    jsonb metrics
  }
  ml_current {
    text kind PK
    uuid run_id FK
  }
  similar_profiles {
    uuid run_id PK,FK
    uuid profile_id PK,FK
    uuid similar_id PK,FK
    int rank
    real score
  }
  potential_partners {
    uuid run_id PK,FK
    uuid profile_id PK,FK
    uuid partner_id PK,FK
    int rank
    real score
    jsonb reasons
  }
  cluster_assignments {
    uuid run_id PK,FK
    uuid profile_id PK,FK
    int cluster_id
    text label
  }
  pipeline_state {
    boolean singleton PK
    bigint data_version
    timestamptz dirty_since
  }
  erasures {
    uuid id PK
    bytea key_hmac
    text status
  }
```

## Assignment §4.2 fields

| Required field | Where it is stored |
|---|---|
| Unique ID | `profiles.id` |
| Name | `profiles.name` |
| Profile type | `profiles.type` |
| Short description | `profiles.description` |
| Sector | `profiles.sector` |
| Skills | `profiles.skills` |
| Products / services | `profiles.services` |
| Region | `profiles.region` |
| Source name and URL | `sources.name`, `sources.base_url`, via `profile_sources` and `source_records` |
| Link to the original profile | `source_records.original_url` |
| Last update | `profiles.updated_at`; per source, `source_records.source_updated_at` |

Optional fields kept: languages (`profiles.languages`), wanted partnerships and
technology needs (`profiles.needs`), website (`profiles.website`).

## Tables the assignment names

| §6 table | Written by |
|---|---|
| `similar_profiles` | Spark similarity job |
| `potential_partners` | Spark matchmaking job |
| `cluster_assignments` | Spark clustering job |
| `sync_runs` | API (`/sync/{source}`) and the worker, one row per import |
