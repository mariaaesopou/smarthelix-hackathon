import type { FastifyReply, FastifyRequest } from "fastify";
import type { RecommendationKind } from "../repositories/profiles.ts";
import type { ProfileQuery, ProfileService } from "../services/profiles.ts";

const notFound = { statusCode: 404, error: "Not Found", message: "Profile not found" };

type IdRequest = FastifyRequest<{ Params: { id: string } }>;
type RecommendationRequest = FastifyRequest<{ Params: { id: string }; Querystring: { limit: number } }>;

export function createProfileController(service: ProfileService) {
  const recommendations = (kind: RecommendationKind) =>
    async (request: RecommendationRequest, reply: FastifyReply) => {
      const found = await service.recommendations(request.params.id, kind, request.query.limit);
      if (found.kind === "found") return found.items;
      if (found.kind === "merged") {
        // Relative to /profiles/{id}/: ../{survivor}/similar, also behind the /api proxy.
        return reply.redirect(`../${encodeURIComponent(found.survivorId)}/${kind}`, 307);
      }
      return reply.code(404).send(notFound);
    };

  return {
    list(request: FastifyRequest<{ Querystring: ProfileQuery }>) {
      return service.search(request.query);
    },

    async get(request: IdRequest, reply: FastifyReply) {
      const found = await service.findById(request.params.id);
      if (found.kind === "found") return found.profile;
      if (found.kind === "merged") {
        // 307, not 308: a merge can be undone (rule 22). A relative Location keeps
        // working behind the web app's /api proxy: /api/profiles/x -> /api/profiles/y.
        return reply.redirect(encodeURIComponent(found.survivorId), 307);
      }
      return reply.code(404).send(notFound);
    },

    similar: recommendations("similar"),
    partners: recommendations("partners"),
  };
}
