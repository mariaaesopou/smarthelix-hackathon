import type { Profile, ProfileCard, Recommendation } from "@smarthelix/shared/generated";

export type ProfileType = Profile["type"];

/** Filters of GET /profiles, already validated by the route. */
export interface SearchFilters {
  q?: string;
  type?: ProfileType;
  sector?: string;
  region?: string;
  skill?: string;
  source?: string;
  limit: number;
  offset: number;
}

export interface SearchResult {
  items: ProfileCard[];
  /** Matching profiles on all pages. */
  total: number;
}

/**
 * Result of looking up one profile. A merged profile points at the profile it
 * was merged into (architecture rule 22); deleted and unknown ids are "missing".
 */
export type ProfileLookup =
  | { kind: "found"; profile: Profile }
  | { kind: "merged"; survivorId: string }
  | { kind: "missing" };

/** similar: the similar_profiles table; partners: potential_partners. */
export type RecommendationKind = "similar" | "partners";

/**
 * Result of asking for a profile's recommendations. Items follow rule 21: a merged
 * target is replaced by its survivor, deleted targets and the profile itself are
 * dropped, each target appears once at its best rank, and ranks restart at 1.
 * No current ML run, or no rows, gives an empty list.
 */
export type RecommendationLookup =
  | { kind: "found"; items: Recommendation[] }
  | { kind: "merged"; survivorId: string }
  | { kind: "missing" };

/** Where profiles come from. Fixtures and the database both implement it. */
export interface ProfileRepository {
  search(filters: SearchFilters): Promise<SearchResult>;
  findById(id: string): Promise<ProfileLookup>;
  recommendations(id: string, kind: RecommendationKind, limit: number): Promise<RecommendationLookup>;
}
