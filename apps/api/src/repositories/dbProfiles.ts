import type { Profile, ProfileCard } from "@smarthelix/shared/generated";
import type pg from "pg";
import type { ProfileLookup, ProfileRepository, SearchFilters, SearchResult } from "./profiles.ts";

/**
 * Filters shared by the page query and the count query. Every value is a bound
 * parameter: $1 q, $2 type, $3 sector, $4 region, $5 skill, $6 source.
 * A NULL parameter switches its filter off.
 *
 * Text match (architecture rule 24): the full-text column, or a name that is
 * similar enough (pg_trgm's <% operator) so small typos in names still match.
 */
const WHERE = `
  p.deleted_at IS NULL AND p.merged_into IS NULL
  AND ($1::text IS NULL
       OR p.search @@ public.f_tsq($1)
       OR public.f_norm($1) <% public.f_norm(p.name))
  AND ($2::text IS NULL OR p.type = $2)
  AND ($3::text IS NULL OR p.sector = $3)
  AND ($4::text IS NULL OR p.region = $4)
  AND ($5::text IS NULL OR p.skills @> ARRAY[$5::text])
  AND ($6::text IS NULL OR EXISTS (
        SELECT 1 FROM profile_sources ps
        JOIN source_records sr ON sr.id = ps.source_record_id
        WHERE ps.profile_id = p.id AND sr.source = $6 AND sr.deleted_at IS NULL))`;

/** Rank (rule 24): 0.7 full-text rank + 0.3 name similarity; name order without q. */
const PAGE_SQL = `
  SELECT p.id, p.type, p.name, p.description, p.sector, p.region, p.skills,
         ARRAY(SELECT DISTINCT sr.source
               FROM profile_sources ps
               JOIN source_records sr ON sr.id = ps.source_record_id
               WHERE ps.profile_id = p.id AND sr.deleted_at IS NULL
               ORDER BY 1) AS sources
  FROM profiles p
  WHERE ${WHERE}
  ORDER BY
    CASE WHEN $1::text IS NULL THEN NULL ELSE
      0.7 * coalesce(ts_rank_cd(p.search, public.f_tsq($1), 1 | 32), 0)
      + 0.3 * word_similarity(public.f_norm($1), public.f_norm(p.name))
    END DESC NULLS LAST,
    CASE WHEN $1::text IS NULL THEN p.name END,
    p.id
  LIMIT $7 OFFSET $8`;

const COUNT_SQL = `SELECT count(*)::int AS total FROM profiles p WHERE ${WHERE}`;

const PROFILE_SQL = `
  SELECT p.id, p.type, p.name, p.description, p.sector, p.region, p.skills, p.services,
         p.needs, p.languages, p.website, p.updated_at, p.deleted_at, p.merged_into,
         coalesce((
           SELECT json_agg(json_build_object('name', s.name, 'url', s.base_url,
                                             'original_url', sr.original_url)
                           ORDER BY s.name, sr.original_url)
           FROM profile_sources ps
           JOIN source_records sr ON sr.id = ps.source_record_id
           JOIN sources s ON s.name = sr.source
           WHERE ps.profile_id = p.id AND sr.deleted_at IS NULL), '[]') AS sources,
         (SELECT json_build_object('id', ca.cluster_id, 'label', ca.label)
          FROM ml_current mc
          JOIN cluster_assignments ca ON ca.run_id = mc.run_id
          WHERE mc.kind = 'clustering' AND ca.profile_id = p.id) AS cluster
  FROM profiles p
  WHERE p.id = $1`;

type ProfileRow = Profile & { deleted_at: Date | null; merged_into: string | null; updated_at: Date };

/** A pool, or one client inside a transaction (the tests roll theirs back). */
export type Queryable = Pick<pg.Pool, "query">;

/** Reads profiles from PostgreSQL with parameterised SQL (no ORM: the search is in SQL functions). */
export function createDbProfileRepository(pool: Queryable): ProfileRepository {
  return {
    async search(f: SearchFilters): Promise<SearchResult> {
      const filters = [f.q ?? null, f.type ?? null, f.sector ?? null, f.region ?? null,
                       f.skill ?? null, f.source ?? null];
      const [page, count] = await Promise.all([
        pool.query<ProfileCard>(PAGE_SQL, [...filters, f.limit, f.offset]),
        pool.query<{ total: number }>(COUNT_SQL, filters),
      ]);
      return { items: page.rows, total: count.rows[0].total };
    },

    async findById(id: string): Promise<ProfileLookup> {
      const { rows } = await pool.query<ProfileRow>(PROFILE_SQL, [id]);
      const row = rows[0];
      if (!row || row.deleted_at) return { kind: "missing" };
      // merged_into is flattened on every merge (rule 6), so it is the survivor.
      if (row.merged_into) return { kind: "merged", survivorId: row.merged_into };
      const { deleted_at: _deleted, merged_into: _merged, ...profile } = row;
      return { kind: "found", profile: { ...profile, updated_at: row.updated_at.toISOString() } };
    },
  };
}
