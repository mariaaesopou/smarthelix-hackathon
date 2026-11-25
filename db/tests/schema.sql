-- Assertions run in a transaction that is always rolled back.
BEGIN;
DO $$
DECLARE p uuid; q uuid; b uuid; r uuid;
BEGIN
  ASSERT (SELECT count(*) = 3 FROM pg_ts_config WHERE cfgname IN ('greek','english','simple')), 'ts configs';
  ASSERT public.f_norm('ΐΰ Ά ΣΧΕΔΙΑΣΜΟΣ') = 'ιυ α σχεδιασμοσ', 'normalisation';
  ASSERT public.f_tsq('και the') IS NULL, 'stop words';
  INSERT INTO profiles(type,name,description,skills,services) VALUES
    ('sme','Zzacme Καφέ','Σχεδιασμός ιστοσελίδων','{"graphic design"}','{branding}') RETURNING id INTO p;
  INSERT INTO profiles(type,name) VALUES ('sme','Zzother') RETURNING id INTO q;
  ASSERT (SELECT search @@ public.f_tsq('designs ιστοσελιδα') FROM profiles WHERE id=p), 'mixed language';
  ASSERT (SELECT search @@ public.f_tsq('ΣΧΕΔΙΑΣΜΟΣ') FROM profiles WHERE id=p), 'upper case Greek';
  ASSERT (SELECT search @@ 'zzacme:A'::tsquery AND search @@ 'branding:B'::tsquery
          AND search @@ 'graphic:B'::tsquery AND search @@ 'σχεδιασμοσ:C'::tsquery
          FROM profiles WHERE id=p), 'field weights';
  ASSERT (SELECT NOT search @@ 'σχεδιασμοσ:AB'::tsquery FROM profiles WHERE id=p), 'weights are exclusive';
  BEGIN
    UPDATE profiles SET merged_into=id WHERE id=p;
    RAISE EXCEPTION 'self merge allowed';
  EXCEPTION WHEN check_violation THEN NULL; END;
  UPDATE ml_batches SET status='failed' WHERE status IN ('queued','running');
  INSERT INTO ml_batches(data_version) VALUES (1) RETURNING id INTO b;
  BEGIN
    INSERT INTO ml_batches(data_version) VALUES (2);
    RAISE EXCEPTION 'two active batches allowed';
  EXCEPTION WHEN unique_violation THEN NULL; END;
  INSERT INTO ml_runs(batch_id,kind,data_version) VALUES (b,'similarity',1) RETURNING id INTO r;
  DELETE FROM ml_current WHERE kind='matching';
  BEGIN
    INSERT INTO ml_current VALUES ('matching',r);
    RAISE EXCEPTION 'wrong kind allowed';
  EXCEPTION WHEN foreign_key_violation THEN NULL; END;
  INSERT INTO similar_profiles VALUES (r,p,q,1,0.5);
  DELETE FROM profiles WHERE id=q;
  ASSERT NOT EXISTS (SELECT 1 FROM similar_profiles WHERE run_id=r), 'target cascade';
END $$;
ROLLBACK;
\echo schema tests passed
