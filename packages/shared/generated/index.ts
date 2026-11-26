// Generated from schemas/. Do not edit; run pnpm generate.

export interface ClusterAssignment {
  profile_id: string;
  cluster_id: number;
  label: string;
}

/**
 * Body of every API error response (Fastify's default shape).
 */
export interface ApiError {
  statusCode: number;
  /**
   * HTTP status text, such as Not Found.
   */
  error: string;
  message: string;
}

export interface EtlJob {
  sync_run_id: string;
}

export interface MlJob {
  batch_id: string;
}

/**
 * Connector output, before resolution.
 */
export interface NormalizedRecord {
  source: string;
  source_id: string;
  original_url: string;
  source_updated_at: string | null;
  type: "sme" | "young_entrepreneur" | "freelancer";
  name: string;
  description: string;
  sector: string | null;
  region: string | null;
  skills: string[];
  services: string[];
  needs: string[];
  languages: string[];
  website: string | null;
}

export interface PotentialPartner {
  profile_id: string;
  partner_id: string;
  rank: number;
  score: number;
  reasons: {
    matched_needs: string[];
  };
}

/**
 * Summary of a profile in result lists, similar profiles and partners.
 */
export interface ProfileCard {
  id: string;
  type: "sme" | "young_entrepreneur" | "freelancer";
  name: string;
  description: string;
  sector: string | null;
  region: string | null;
  skills: string[];
  /**
   * Names of the sources this profile was built from.
   *
   * @minItems 1
   */
  sources: [string, ...string[]];
}

/**
 * Response of GET /profiles: one page of search results.
 */
export interface ProfilePage {
  items: ProfileCard[];
  page: number;
  per_page: number;
  /**
   * Number of matching profiles on all pages.
   */
  total: number;
}

export interface Profile {
  id: string;
  type: "sme" | "young_entrepreneur" | "freelancer";
  name: string;
  description: string;
  sector: string | null;
  region: string | null;
  skills: string[];
  services: string[];
  needs: string[];
  languages: string[];
  website: string | null;
  updated_at: string;
  /**
   * @minItems 1
   */
  sources: [
    {
      name: string;
      url: string;
      original_url: string;
    },
    ...{
      name: string;
      url: string;
      original_url: string;
    }[]
  ];
  /**
   * Current clustering result, or null before the first clustering run.
   */
  cluster: {
    id: number;
    label: string;
  } | null;
}

/**
 * One item of GET /profiles/{id}/similar or GET /profiles/{id}/partners.
 */
export interface Recommendation {
  profile: ProfileCard;
  rank: number;
  score: number;
  /**
   * Needs of the requested profile that this one offers. Empty for similar profiles.
   */
  matched_needs: string[];
}

export interface ResolutionJob {
  sync_run_id: string;
}

export interface SimilarProfile {
  profile_id: string;
  similar_id: string;
  rank: number;
  score: number;
}

/**
 * One profile as source A (SME platform) sends it from GET /a/profiles. The connector maps it to NormalizedRecord.
 */
export interface SourceARecord {
  /**
   * Maps to source_id.
   */
  id: string;
  /**
   * Maps to name.
   */
  company_name: string;
  /**
   * SME maps to type sme, Startup to young_entrepreneur.
   */
  category: "SME" | "Startup";
  /**
   * Maps to description.
   */
  summary: string;
  /**
   * Maps to sector.
   */
  industry: string | null;
  /**
   * Maps to region.
   */
  location: string | null;
  /**
   * Maps to skills.
   */
  capabilities: string[];
  /**
   * Maps to services.
   */
  products: string[];
  /**
   * Maps to needs.
   */
  looking_for: string[];
  languages: string[];
  website: string | null;
  /**
   * Maps to original_url.
   */
  profile_url: string;
  /**
   * Maps to source_updated_at; also the updated_since cursor.
   */
  last_modified: string;
}

/**
 * One freelancer as source B sends it in /b/export.json. The connector maps it to NormalizedRecord; every record has type freelancer.
 */
export interface SourceBRecord {
  /**
   * Maps to source_id.
   */
  ref: string;
  /**
   * Maps to name.
   */
  fullName: string;
  /**
   * Maps to description.
   */
  bio: string;
  /**
   * Maps to sector.
   */
  field: string | null;
  /**
   * Maps to region.
   */
  area: string | null;
  /**
   * Maps to skills.
   */
  expertise: string[];
  /**
   * Maps to services.
   */
  offers: string[];
  /**
   * Maps to needs.
   */
  seeking: string[];
  /**
   * Maps to languages.
   */
  speaks: string[];
  /**
   * Maps to website.
   */
  homepage: string | null;
  /**
   * Maps to original_url.
   */
  profileLink: string;
  /**
   * Maps to source_updated_at.
   */
  modifiedAt: string;
  /**
   * Not in the common schema; the connector must not store it.
   */
  hourlyRate: number;
  /**
   * Not in the common schema; the connector must not store it.
   */
  availability: "full-time" | "part-time" | "weekends";
}

/**
 * Response of POST /sync/{source}: one import run and its progress.
 */
export interface SyncRun {
  id: string;
  source: string;
  mode: "full" | "incremental";
  status: "queued" | "etl_running" | "etl_done" | "resolved" | "failed";
  /**
   * Records fetched, inserted, updated and so on.
   */
  counts: {
    [k: string]: number;
  };
  error_code: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}
