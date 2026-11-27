import type {ApiClient} from "./client";
import {NotFoundError, type Profile, type SearchParams} from "./types";
import data from "./mock/profiles.json";

const profiles = data as Profile[];
const DEFAULT_LIMIT = 20;

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

// Pretend to be a network call, so loading states are visible.
function delay<T>(value: T, ms = 300): Promise<T> {
    return new Promise((resolve) => setTimeout(() => resolve(value), ms));
}

export const mockClient: ApiClient = {
    async searchProfiles(params) {
        const limit = params.limit ?? DEFAULT_LIMIT;
        const offset = params.offset ?? 0;
        const hits = profiles.filter((p) => matches(p, params));
        if (!params.q) hits.sort((a, b) => a.name.localeCompare(b.name));
        return delay({ items: hits.slice(offset, offset + limit), total: hits.length });
    },

    async getProfile(id) {
        const profile = profiles.find((p) => p.id === id);
        await delay(null);
        if (!profile) throw new NotFoundError(`Profile ${id} not found`);
        return profile;
    },
};
