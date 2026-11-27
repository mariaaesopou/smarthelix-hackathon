import type { FastifyReply, FastifyRequest } from "fastify";
import type { ProfileQuery, ProfileService } from "../services/profiles.ts";

export function createProfileController(service: ProfileService) {
  return {
    list(request: FastifyRequest<{ Querystring: ProfileQuery }>) {
      return service.search(request.query);
    },

    async get(request: FastifyRequest<{ Params: { id: string } }>, reply: FastifyReply) {
      const found = await service.findById(request.params.id);
      if (found.kind === "found") return found.profile;
      if (found.kind === "merged") {
        // 307, not 308: a merge can be undone (rule 22). A relative Location keeps
        // working behind the web app's /api proxy: /api/profiles/x -> /api/profiles/y.
        return reply.redirect(encodeURIComponent(found.survivorId), 307);
      }
      return reply.code(404).send({ statusCode: 404, error: "Not Found", message: "Profile not found" });
    },
  };
}
