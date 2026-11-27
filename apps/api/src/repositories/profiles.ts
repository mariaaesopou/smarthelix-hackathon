import type { Profile, ProfileCard } from "@smarthelix/shared/generated";

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

/** Where profiles come from. Fixtures and the database both implement it. */
export interface ProfileRepository {
  search(filters: SearchFilters): Promise<SearchResult>;
  findById(id: string): Promise<ProfileLookup>;
}
