import Fastify, { type FastifyServerOptions } from "fastify";
import type { ProfileRepository } from "./repositories/profiles.ts";
import { profileRoutes } from "./routes/profiles.ts";
import { registerSharedSchemas } from "./schemas.ts";
import { createProfileService } from "./services/profiles.ts";

export interface AppOptions {
  profiles: ProfileRepository;
  /** Throws when a dependency is down; /health then answers 503. */
  checkHealth?: () => Promise<void>;
  logger?: FastifyServerOptions["logger"];
}

/** Builds the API without listening, so tests can call it with app.inject(). */
export async function buildApp({ profiles, checkHealth, logger = false }: AppOptions) {
  const app = Fastify({ logger });
  registerSharedSchemas(app);

  app.get("/health", async (_request, reply) => {
    try {
      await checkHealth?.();
      return { status: "ok" };
    } catch {
      return reply.code(503).send({ status: "unavailable" });
    }
  });

  await app.register(profileRoutes(createProfileService(profiles)));
  return app;
}
