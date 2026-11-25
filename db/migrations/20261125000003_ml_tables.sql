-- migrate:up
CREATE TABLE pipeline_state (
  singleton      boolean PRIMARY KEY DEFAULT true CHECK (singleton),
  data_version   bigint NOT NULL DEFAULT 0,
  dirty_since    timestamptz,
  last_change_at timestamptz
);
INSERT INTO pipeline_state DEFAULT VALUES;

CREATE TABLE ml_batches (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  data_version bigint NOT NULL,
  status       text NOT NULL DEFAULT 'queued'
               CHECK (status IN ('queued', 'running', 'succeeded', 'failed')),
  attempts     integer NOT NULL DEFAULT 0,
  created_at   timestamptz NOT NULL DEFAULT now(),
  finished_at  timestamptz
);
-- Debounce backstop: never two pending or running ML batches.
CREATE UNIQUE INDEX ml_batches_one_active ON ml_batches ((true))
  WHERE status IN ('queued', 'running');

CREATE TABLE ml_runs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  batch_id     uuid NOT NULL REFERENCES ml_batches(id),
  kind         text NOT NULL CHECK (kind IN ('similarity', 'matching', 'clustering')),
  data_version bigint NOT NULL,
  status       text NOT NULL DEFAULT 'running'
               CHECK (status IN ('running', 'succeeded', 'failed')),
  params       jsonb NOT NULL DEFAULT '{}',
  metrics      jsonb NOT NULL DEFAULT '{}',
  started_at   timestamptz NOT NULL DEFAULT now(),
  finished_at  timestamptz,
  UNIQUE (kind, id)
);

-- The composite key stops a kind pointing at another kind's run.
CREATE TABLE ml_current (
  kind   text PRIMARY KEY,
  run_id uuid NOT NULL,
  FOREIGN KEY (kind, run_id) REFERENCES ml_runs (kind, id)
);

CREATE TABLE similar_profiles (
  run_id     uuid NOT NULL REFERENCES ml_runs(id) ON DELETE CASCADE,
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  similar_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  rank       integer NOT NULL CHECK (rank > 0),
  score      real NOT NULL,
  PRIMARY KEY (run_id, profile_id, similar_id),
  CHECK (profile_id <> similar_id)
);
CREATE INDEX similar_profiles_profile ON similar_profiles (profile_id);
CREATE INDEX similar_profiles_target ON similar_profiles (similar_id);

CREATE TABLE potential_partners (
  run_id     uuid NOT NULL REFERENCES ml_runs(id) ON DELETE CASCADE,
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  partner_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  rank       integer NOT NULL CHECK (rank > 0),
  score      real NOT NULL,
  reasons    jsonb NOT NULL DEFAULT '{}',   -- skills only, never names
  PRIMARY KEY (run_id, profile_id, partner_id),
  CHECK (profile_id <> partner_id)
);
CREATE INDEX potential_partners_profile ON potential_partners (profile_id);
CREATE INDEX potential_partners_target ON potential_partners (partner_id);

CREATE TABLE cluster_assignments (
  run_id     uuid NOT NULL REFERENCES ml_runs(id) ON DELETE CASCADE,
  profile_id uuid NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
  cluster_id integer NOT NULL,
  label      text NOT NULL,                 -- never built from names
  PRIMARY KEY (run_id, profile_id)
);
CREATE INDEX cluster_assignments_profile ON cluster_assignments (profile_id);

-- migrate:down
DROP TABLE cluster_assignments, potential_partners, similar_profiles,
           ml_current, ml_runs, ml_batches, pipeline_state;
