import type {Profile} from "../../../../packages/shared/generated";

// The shapes the team agreed on, generated from packages/shared/schemas.
export type {
    ClusterAssignment,
    PotentialPartner,
    Profile,
    SimilarProfile,
} from "../../../../packages/shared/generated";

export type ProfileType = Profile["type"];

export const TYPE_LABELS: Record<ProfileType, string> = {
    sme: "SME",
    young_entrepreneur: "Young entrepreneur",
    freelancer: "Freelancer",
};

// Query parameters of GET /profiles.
export interface SearchParams {
    q?: string;
    type?: ProfileType;
    sector?: string;
    region?: string;
    limit?: number; // at most 50
    offset?: number; // at most 1000
}

// One page of results plus the total number of matches.
export interface Page<T> {
    items: T[];
    total: number;
}

// Thrown when a profile does not exist, so pages can show "not found".
export class NotFoundError extends Error {}
