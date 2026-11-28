import Fastify, { type FastifyServerOptions } from "fastify";
import type { JobQueue } from "./queue.ts";
import type { ProfileRepository } from "./repositories/profiles.ts";
import type { SyncRunRepository } from "./repositories/syncRuns.ts";
import { profileRoutes } from "./routes/profiles.ts";
import { syncRoutes } from "./routes/sync.ts";
import { registerSharedSchemas } from "./schemas.ts";
import { createProfileService } from "./services/profiles.ts";
import { createSyncService } from "./services/sync.ts";

export interface AppOptions {
  profiles: ProfileRepository;
  /** Enables /sync; it needs the database and the job queue, so fixture mode leaves it out. */
  sync?: { runs: SyncRunRepository; queue: JobQueue };
  /** Throws when a dependency is down; /health then answers 503. */
  checkHealth?: () => Promise<void>;
  logger?: FastifyServerOptions["logger"];
}

/** Builds the API without listening, so tests can call it with app.inject(). */
export async function buildApp({ profiles, sync, checkHealth, logger = false }: AppOptions) {
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
  if (sync) await app.register(syncRoutes(createSyncService(sync.runs, sync.queue)));
  return app;
}
