-- migrate:up
-- The two sources the connectors import from. Every sync_runs and source_records
-- row needs its source here, so they belong in a migration, not only in a seed.
-- base_url is shown to users as the source link, so it must open in a browser;
-- the worker reaches the sources through MOCK_SOURCES_URL instead.
INSERT INTO sources (name, base_url, terms_note) VALUES
  ('source_a', 'http://localhost:4000/a', 'Synthetic SME platform'),
  ('source_b', 'http://localhost:4000/b', 'Synthetic freelancer export')
ON CONFLICT (name) DO UPDATE
  SET base_url = EXCLUDED.base_url, terms_note = EXCLUDED.terms_note;

-- migrate:down
-- Removes a source only while nothing refers to it.
DELETE FROM sources s
WHERE s.name IN ('source_a', 'source_b')
  AND NOT EXISTS (SELECT 1 FROM sync_runs r WHERE r.source = s.name)
  AND NOT EXISTS (SELECT 1 FROM source_records r WHERE r.source = s.name);
