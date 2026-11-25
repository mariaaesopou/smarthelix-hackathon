-- migrate:up
CREATE EXTENSION unaccent WITH SCHEMA public;
CREATE EXTENSION pg_trgm WITH SCHEMA public;

-- unaccent() is STABLE, so generated columns and indexes need this wrapper.
-- After changing unaccent rules or any function here, rebuild profiles.search
-- and profiles_name_trgm.
CREATE FUNCTION public.f_unaccent(text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS
$$ SELECT public.unaccent('public.unaccent'::regdictionary, normalize($1, NFC)) $$;

CREATE FUNCTION public.f_norm(text) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS
$$ SELECT translate(lower(public.f_unaccent($1)), 'ς', 'σ') $$;

CREATE FUNCTION public.f_arr(text[]) RETURNS text
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS
$$ SELECT array_to_string($1, ' ') $$;

CREATE FUNCTION public.f_tsv(text) RETURNS tsvector
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS
$$ SELECT to_tsvector('pg_catalog.greek'::regconfig,   public.f_norm($1))
       || to_tsvector('pg_catalog.english'::regconfig, public.f_norm($1))
       || to_tsvector('pg_catalog.simple'::regconfig,  public.f_norm($1)) $$;

-- ORs the configs per token, then ANDs the tokens, so mixed-language queries
-- match. Returns NULL when only stop words remain. Plain words only: no
-- phrases or negation. The Greek list exists because the greek config has none.
CREATE FUNCTION public.f_tsq(q text) RETURNS tsquery
LANGUAGE plpgsql STABLE STRICT PARALLEL SAFE
SET client_min_messages = error AS $$
DECLARE
  result tsquery;
  token text;
  part tsquery;
BEGIN
  FOREACH token IN ARRAY regexp_split_to_array(
    trim(regexp_replace(public.f_norm(q), '[^[:alnum:]]+', ' ', 'g')), '\s+')
  LOOP
    CONTINUE WHEN token = ''
      OR token = ANY (ARRAY[
        'ο','η','το','οι','τα','του','τησ','των','τον','την','τη','τουσ','τισ',
        'στο','στη','στην','στον','στουσ','στισ','στα','και','κι','με','για',
        'απο','σε','ειναι'])
      OR numnode(plainto_tsquery('pg_catalog.english', token)) = 0;
    part := plainto_tsquery('pg_catalog.greek', token)
         || plainto_tsquery('pg_catalog.english', token)
         || plainto_tsquery('pg_catalog.simple', token);
    result := CASE WHEN result IS NULL THEN part ELSE result && part END;
  END LOOP;
  RETURN result;
END $$;

-- migrate:down
DROP FUNCTION public.f_tsq(text);
DROP FUNCTION public.f_tsv(text);
DROP FUNCTION public.f_arr(text[]);
DROP FUNCTION public.f_norm(text);
DROP FUNCTION public.f_unaccent(text);
DROP EXTENSION pg_trgm;
DROP EXTENSION unaccent;
