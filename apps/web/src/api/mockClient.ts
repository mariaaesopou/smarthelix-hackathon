import type {ApiClient} from "./client";
import {NotFoundError, type Profile, type ProfileCard, type SearchParams} from "./types";
import data from "./mock/profiles.json";

const profiles = data as Profile[];
const DEFAULT_PER_PAGE = 20;
const MAX_PER_PAGE = 100;

// Lower case and strip accents, so "Αρτοποιείο" and "αρτοποιειο" match.
function normalize(text: string): string {
    return text.toLowerCase().normalize("NFD").replace(/\p{M}/gu, "");
}

function searchableText(p: Profile): string {
    return normalize(
        [p.name, p.description, p.sector ?? "", p.region ?? "", ...p.skills, ...p.services].join(" "),
    );
}

function matches(p: Profile, params: SearchParams): boolean {
    if (params.type && p.type !== params.type) return false;
    if (params.sector && p.sector !== params.sector) return false;
    if (params.region && p.region !== params.region) return false;
    if (!params.q) return true;
    const text = searchableText(p);
    // Every word of the query must appear somewhere, like the real API.
    return normalize(params.q)
        .split(/\s+/)
        .filter(Boolean)
        .every((word) => text.includes(word));
}

// The short form GET /profiles returns for each result.
function toCard(p: Profile): ProfileCard {
    const [first, ...rest] = p.sources;
    return {
        id: p.id,
        type: p.type,
        name: p.name,
        description: p.description,
        sector: p.sector,
        region: p.region,
        skills: p.skills,
        sources: [first.name, ...rest.map((s) => s.name)],
    };
}

// Pretend to be a network call, so loading states are visible.
function delay<T>(value: T, ms = 300): Promise<T> {
    return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export const mockClient: ApiClient = {
    async searchProfiles(params) {
        // Same limits as the API: page starts at 1, per_page is 1 to 100.
        const page = Math.max(1, Math.floor(params.page ?? 1));
        const per_page = Math.min(MAX_PER_PAGE, Math.max(1, Math.floor(params.per_page ?? DEFAULT_PER_PAGE)));
        const hits = profiles.filter((p) => matches(p, params));
        if (!params.q) hits.sort((a, b) => a.name.localeCompare(b.name));
        const start = (page - 1) * per_page;
        return delay({
            items: hits.slice(start, start + per_page).map(toCard),
            page,
            per_page,
            total: hits.length,
        });
    },

    async getProfile(id) {
        const profile = profiles.find((p) => p.id === id);
        await delay(null);
        if (!profile) throw new NotFoundError(`Profile ${id} not found`);
        return profile;
    },
};
