// Generated from schemas/. Do not edit; run pnpm generate.

export interface ClusterAssignment {
  profile_id: string;
  cluster_id: number;
  label: string;
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
