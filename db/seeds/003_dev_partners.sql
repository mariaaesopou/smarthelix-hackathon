-- Hand-made potential partners for every profile, until the Spark matchmaking job
-- (Role 2, compute_partners) writes real ones. Safe to run repeatedly.
--
-- Rule: B is a partner of A when B offers (skills or services) something A needs.
-- Score = share of A's needs that B covers; ties go to the profile with more
-- offers. Terms are compared case-insensitively and without accents (f_norm).
-- The rows live under their own ML run and become the current "matching" run, so
-- the first real Spark run replaces them (architecture rule 17).
BEGIN;

INSERT INTO ml_batches (id, data_version, status, finished_at)
VALUES ('c0000000-0000-4000-8000-0000000000aa', 0, 'succeeded', now())
ON CONFLICT DO NOTHING;

INSERT INTO ml_runs (id, batch_id, kind, data_version, status, params, finished_at)
VALUES ('d0000000-0000-4000-8000-0000000000aa', 'c0000000-0000-4000-8000-0000000000aa',
        'matching', 0, 'succeeded', '{"method": "hand-made: needs matched to offers"}', now())
ON CONFLICT DO NOTHING;

DELETE FROM potential_partners WHERE run_id = 'd0000000-0000-4000-8000-0000000000aa';

WITH live AS (
  SELECT id, needs, skills || services AS offers
  FROM profiles WHERE deleted_at IS NULL AND merged_into IS NULL
),
need AS (
  SELECT l.id, n AS term, public.f_norm(n) AS norm, cardinality(l.needs) AS total
  FROM live l, unnest(l.needs) AS n
),
offer AS (
  SELECT DISTINCT l.id, public.f_norm(o) AS norm, cardinality(l.offers) AS offers
  FROM live l, unnest(l.offers) AS o
),
pairs AS (
  SELECT n.id AS profile_id, o.id AS partner_id, max(o.offers) AS offers, max(n.total) AS total,
         array_agg(DISTINCT n.term ORDER BY n.term) AS matched
  FROM need n JOIN offer o ON o.norm = n.norm AND o.id <> n.id
  GROUP BY n.id, o.id
),
ranked AS (
  SELECT *, row_number() OVER (PARTITION BY profile_id
                               ORDER BY cardinality(matched) DESC, offers DESC, partner_id) AS rank
  FROM pairs
)
INSERT INTO potential_partners (run_id, profile_id, partner_id, rank, score, reasons)
SELECT 'd0000000-0000-4000-8000-0000000000aa', profile_id, partner_id, rank,
       round(cardinality(matched)::numeric / total, 3),
       jsonb_build_object('matched_needs', to_jsonb(matched))
FROM ranked
WHERE rank <= 20;

INSERT INTO ml_current (kind, run_id) VALUES ('matching', 'd0000000-0000-4000-8000-0000000000aa')
ON CONFLICT (kind) DO UPDATE SET run_id = EXCLUDED.run_id;

COMMIT;
