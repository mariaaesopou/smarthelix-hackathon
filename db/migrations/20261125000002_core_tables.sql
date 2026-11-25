-- migrate:up
CREATE TABLE sources (
  name       text PRIMARY KEY,
  base_url   text NOT NULL,
  terms_note text
);

CREATE TABLE sync_runs (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source      text NOT NULL REFERENCES sources(name),
  mode        text NOT NULL CHECK (mode IN ('full', 'incremental')),
  status      text NOT NULL DEFAULT 'queued'
              CHECK (status IN ('queued', 'etl_running', 'etl_done', 'resolved', 'failed')),
  cursor      text,
  watermark   timestamptz,
  counts      jsonb NOT NULL DEFAULT '{}',
  error_code  text,
  created_at  timestamptz NOT NULL DEFAULT now(),
  started_at  timestamptz,
  finished_at timestamptz
);
-- One queued or running ETL per source.
CREATE UNIQUE INDEX sync_runs_one_active ON sync_runs (source)
  WHERE status IN ('queued', 'etl_running');
CREATE INDEX sync_runs_by_source ON sync_runs (source, created_at DESC);

CREATE TABLE source_records (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  source            text NOT NULL REFERENCES sources(name),
  source_id         text NOT NULL,
  raw               jsonb NOT NULL,   -- allowlisted fields only
  hash              text NOT NULL,
  resolved_hash     text,             -- NULL forces re-resolution
  original_url      text NOT NULL,
  source_updated_at timestamptz,
  fetched_at        timestamptz NOT NULL DEFAULT now(),
  last_seen_run_id  uuid REFERENCES sync_runs(id) ON DELETE SET NULL,
  deleted_at        timestamptz,
  UNIQUE (source, source_id)
);

CREATE TABLE profiles (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type        text NOT NULL CHECK (type IN ('sme', 'young_entrepreneur', 'freelancer')),
  name        text NOT NULL CHECK (name <> ''),
  description text NOT NULL DEFAULT '',
  sector      text,
  region      text,
  skills      text[] NOT NULL DEFAULT '{}',
  services    text[] NOT NULL DEFAULT '{}',
  needs       text[] NOT NULL DEFAULT '{}',
  languages   text[] NOT NULL DEFAULT '{}',
  website     text,
  updated_at  timestamptz NOT NULL DEFAULT now(),
  deleted_at  timestamptz,
  merged_into uuid REFERENCES profiles(id),
  search      tsvector NOT NULL GENERATED ALWAYS AS (
       setweight(public.f_tsv(name), 'A')
    || setweight(public.f_tsv(public.f_arr(skills)), 'B')
    || setweight(public.f_tsv(public.f_arr(services)), 'B')
    || setweight(public.f_tsv(description), 'C')
  ) STORED,
  CHECK (merged_into <> id)
);
CREATE INDEX profiles_search ON profiles USING gin (search);
CREATE INDEX profiles_name_trgm ON profiles USING gin (public.f_norm(name) gin_trgm_ops);
CREATE INDEX profiles_skills ON profiles USING gin (skills);
CREATE INDEX profiles_filters ON profiles (type, sector, region)
  WHERE deleted_at IS NULL AND merged_into IS NULL;
CREATE INDEX profiles_merged_into ON profiles (merged_into) WHERE merged_into IS NOT NULL;

CREATE TABLE profile_sources (
  source_record_id uuid PRIMARY KEY REFERENCES source_records(id) ON DELETE CASCADE,
  profile_id       uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  match_method     text NOT NULL CHECK (match_method IN ('new', 'name_domain', 'manual')),
  confidence       real NOT NULL CHECK (confidence BETWEEN 0 AND 1)
);
CREATE INDEX profile_sources_profile ON profile_sources (profile_id);

CREATE TABLE match_candidates (
  record_id  uuid NOT NULL REFERENCES source_records(id) ON DELETE CASCADE,
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  score      real NOT NULL,
  status     text NOT NULL DEFAULT 'pending'
             CHECK (status IN ('pending', 'accepted', 'rejected')),
  PRIMARY KEY (record_id, profile_id)
);

-- Blocklist. Holds an HMAC, never the plain (source, source_id).
CREATE TABLE erasures (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  key_hmac     bytea NOT NULL UNIQUE CHECK (octet_length(key_hmac) = 32),
  status       text NOT NULL DEFAULT 'blocked' CHECK (status IN ('blocked', 'completed')),
  requested_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);

-- migrate:down
DROP TABLE erasures, match_candidates, profile_sources, profiles,
           source_records, sync_runs, sources;
