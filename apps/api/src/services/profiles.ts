import type { ProfilePage } from "@smarthelix/shared/generated";
import type { ProfileLookup, ProfileRepository, ProfileType } from "../repositories/profiles.ts";

export const DEFAULT_PER_PAGE = 20;
export const MAX_PER_PAGE = 100;
/** Capped OFFSET pagination (architecture rule 23): narrow the search instead of paging deeper. */
export const MAX_OFFSET = 1000;

export interface ProfileQuery {
  q?: string;
  type?: ProfileType;
  sector?: string;
  region?: string;
  skill?: string;
  source?: string;
  page: number;
  per_page: number;
}

/** A client error the API reports as 400. Fastify reads statusCode. */
export class BadRequestError extends Error {
  readonly statusCode = 400;
}

export interface ProfileService {
  search(query: ProfileQuery): Promise<ProfilePage>;
  findById(id: string): Promise<ProfileLookup>;
}

export function createProfileService(repository: ProfileRepository): ProfileService {
  return {
    async search({ page, per_page, q, ...filters }) {
      const offset = (page - 1) * per_page;
      if (offset > MAX_OFFSET) {
        throw new BadRequestError(
          `page ${page} is too deep: at most ${MAX_OFFSET} results can be skipped; narrow the search`,
        );
      }
      const text = q?.trim();
      const { items, total } = await repository.search({
        ...filters,
        q: text ? text : undefined,
        limit: per_page,
        offset,
      });
      return { items, page, per_page, total };
    },

    findById: (id) => repository.findById(id),
  };
}
