import type { Profile, ProfileCard } from "@smarthelix/shared/generated";
import data from "./fixtures/profiles.json" with { type: "json" };
import type { ProfileLookup, ProfileRepository, SearchFilters, SearchResult } from "./profiles.ts";

interface FixtureFile {
  profiles: Profile[];
  /** Merged profile id -> the profile it was merged into. */
  merged: Record<string, string>;
}

/** Lower case, no Greek accents, final sigma as sigma: like f_norm in the database. */
export function normalize(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().replaceAll("ς", "σ");
}

function toCard(p: Profile): ProfileCard {
  return {
    id: p.id,
    type: p.type,
    name: p.name,
    description: p.description,
    sector: p.sector,
    region: p.region,
    skills: p.skills,
    // A profile has at least one source (schema minItems 1), so neither has this list.
    sources: [...new Set(p.sources.map((s) => s.name))].sort() as ProfileCard["sources"],
  };
}

function matches(p: Profile, f: SearchFilters): boolean {
  if (f.type && p.type !== f.type) return false;
  if (f.sector && p.sector !== f.sector) return false;
  if (f.region && p.region !== f.region) return false;
  if (f.skill && !p.skills.includes(f.skill)) return false;
  if (f.source && !p.sources.some((s) => s.name === f.source)) return false;
  if (!f.q) return true;
  const text = normalize([p.name, p.description, ...p.skills, ...p.services].join(" "));
  return normalize(f.q).split(/\s+/).filter(Boolean).every((word) => text.includes(word));
}

/** Serves the profiles in fixtures/profiles.json, so the web app can start before the database. */
// JSON imports widen literals ("sme" becomes string), so TypeScript cannot check the
// file itself; tests/profiles.test.ts validates every fixture against profile.json.
export function createFixtureProfileRepository(
  file: FixtureFile = data as unknown as FixtureFile,
): ProfileRepository {
  const byId = new Map(file.profiles.map((p) => [p.id, p]));
  const live = [...file.profiles].sort((a, b) => a.name.localeCompare(b.name) || a.id.localeCompare(b.id));

  return {
    async search(f: SearchFilters): Promise<SearchResult> {
      const hits = live.filter((p) => matches(p, f));
      return { items: hits.slice(f.offset, f.offset + f.limit).map(toCard), total: hits.length };
    },

    async findById(id: string): Promise<ProfileLookup> {
      const survivorId = file.merged[id];
      if (survivorId) return { kind: "merged", survivorId };
      const profile = byId.get(id);
      return profile ? { kind: "found", profile } : { kind: "missing" };
    },
  };
}
