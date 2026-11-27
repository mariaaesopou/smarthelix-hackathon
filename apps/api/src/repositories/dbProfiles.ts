import type { Profile, ProfileCard, Recommendation } from "@smarthelix/shared/generated";
import type pg from "pg";
import type {
  ProfileLookup, ProfileRepository, RecommendationKind, RecommendationLookup, SearchFilters, SearchResult,
} from "./profiles.ts";

/** The ProfileCard columns of profile `p`; shared by search and recommendations. */
const CARD_COLUMNS = `
  p.id, p.type, p.name, p.description, p.sector, p.region, p.skills,
  ARRAY(SELECT DISTINCT sr.source
        FROM profile_sources ps
        JOIN source_records sr ON sr.id = ps.source_record_id
        WHERE ps.profile_id = p.id AND sr.deleted_at IS NULL
        ORDER BY 1) AS sources`;

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
  SELECT ${CARD_COLUMNS}
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

/**
 * Recommendations of profile $1 from the current run of one ML kind, limited to $2.
 * Rule 21: a merged target becomes its survivor (merged_into is flattened, rule 6),
 * each target keeps its best rank, deleted targets and the profile itself are
 * dropped, and ranks are renumbered from 1. Only the run in ml_current is read,
 * so a half-written run is never visible (rule 17).
 */
function recommendationSql(table: string, targetColumn: string, matchedNeeds: string): string {
  return `
  WITH rows AS (
    SELECT coalesce(t.merged_into, t.id) AS target_id, m.rank, m.score, ${matchedNeeds} AS matched_needs
    FROM ml_current mc
    JOIN ${table} m ON m.run_id = mc.run_id
    JOIN profiles t ON t.id = m.${targetColumn}
    WHERE mc.kind = $3 AND m.profile_id = $1
  ),
  best AS (
    SELECT DISTINCT ON (target_id) target_id, rank, score, matched_needs
    FROM rows
    ORDER BY target_id, rank
  )
  SELECT json_build_object(${CARD_JSON}) AS profile,
         row_number() OVER (ORDER BY b.rank, p.id)::int AS rank,
         b.score, b.matched_needs
  FROM best b
  JOIN profiles p ON p.id = b.target_id
  WHERE p.deleted_at IS NULL AND p.merged_into IS NULL AND p.id <> $1
  ORDER BY b.rank, p.id
  LIMIT $2`;
}

/** CARD_COLUMNS as a JSON object, for the nested profile of a recommendation. */
const CARD_JSON = `
  'id', p.id, 'type', p.type, 'name', p.name, 'description', p.description,
  'sector', p.sector, 'region', p.region, 'skills', p.skills,
  'sources', ARRAY(SELECT DISTINCT sr.source
                   FROM profile_sources ps
                   JOIN source_records sr ON sr.id = ps.source_record_id
                   WHERE ps.profile_id = p.id AND sr.deleted_at IS NULL
                   ORDER BY 1)`;

const RECOMMENDATION_SQL: Record<RecommendationKind, { sql: string; mlKind: string }> = {
  similar: {
    sql: recommendationSql("similar_profiles", "similar_id", "ARRAY[]::text[]"),
    mlKind: "similarity",
  },
  partners: {
    // reasons holds {"matched_needs": [...]} (potential-partner.json); missing means none.
    sql: recommendationSql("potential_partners", "partner_id",
      "ARRAY(SELECT jsonb_array_elements_text(coalesce(m.reasons -> 'matched_needs', '[]')))"),
    mlKind: "matching",
  },
};

const STATE_SQL = "SELECT deleted_at, merged_into FROM profiles WHERE id = $1";

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

    async recommendations(id: string, kind: RecommendationKind, limit: number): Promise<RecommendationLookup> {
      const { rows: [state] } = await pool.query<{ deleted_at: Date | null; merged_into: string | null }>(
        STATE_SQL, [id]);
      if (!state || state.deleted_at) return { kind: "missing" };
      if (state.merged_into) return { kind: "merged", survivorId: state.merged_into };
      const { sql, mlKind } = RECOMMENDATION_SQL[kind];
      const { rows } = await pool.query<Recommendation>(sql, [id, limit, mlKind]);
      return { kind: "found", items: rows };
    },
  };
}
