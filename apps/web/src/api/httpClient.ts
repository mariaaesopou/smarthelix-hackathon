import type {ApiClient} from "./client";
import {NotFoundError, type Page, type Profile, type SearchParams} from "./types";

// vite.config.ts forwards /api/* to the API container (http://api:3000).
const BASE_URL = "/api";

async function getJson<T>(path: string): Promise<T> {
    const res = await fetch(`${BASE_URL}${path}`);
    if (res.status === 404) throw new NotFoundError(`Not found: ${path}`);
    if (!res.ok) throw new Error(`API error ${res.status} on ${path}`);
    return (await res.json()) as T;
}

// { q: "design", type: undefined, limit: 20 } becomes "?q=design&limit=20".
function toQueryString(params: SearchParams): string {
    const qs = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
        if (value !== undefined && value !== "") qs.set(key, String(value));
    }
    const text = qs.toString();
    return text ? `?${text}` : "";
}

export const httpClient: ApiClient = {
    searchProfiles: (params) => getJson<Page<Profile>>(`/profiles${toQueryString(params)}`),
    getProfile: (id) => getJson<Profile>(`/profiles/${encodeURIComponent(id)}`),
};
