import type {Profile} from "@smarthelix/shared/generated";

// The shapes the team agreed on, generated from packages/shared/schemas.
export type {
    Profile,
    ProfileCard,
    ProfilePage,
    Recommendation,
} from "@smarthelix/shared/generated";

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
    page?: number; // starts at 1
    per_page?: number; // 1 to 100
}

// Thrown when a profile does not exist, so pages can show "not found".
export class NotFoundError extends Error {}
