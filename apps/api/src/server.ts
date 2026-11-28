import pg from "pg";
import { buildApp } from "./app.ts";
import { createBullQueue } from "./queue.ts";
import { createDbProfileRepository } from "./repositories/dbProfiles.ts";
import { createFixtureProfileRepository } from "./repositories/fixtureProfiles.ts";
import { createDbSyncRunRepository } from "./repositories/syncRuns.ts";

// PROFILES_SOURCE=fixtures serves the files in src/repositories/fixtures without a database.
const source = process.env.PROFILES_SOURCE ?? "database";
if (source !== "database" && source !== "fixtures") {
  throw new Error(`PROFILES_SOURCE must be "database" or "fixtures", not "${source}"`);
}

const pool = source === "database" ? new pg.Pool({ connectionString: process.env.DATABASE_URL }) : null;
// /sync needs both the database and the job queue (Redis).
const queue = pool && process.env.REDIS_URL ? createBullQueue(process.env.REDIS_URL) : null;

const app = await buildApp({
  profiles: pool ? createDbProfileRepository(pool) : createFixtureProfileRepository(),
  sync: pool && queue ? { runs: createDbSyncRunRepository(pool), queue } : undefined,
  checkHealth: pool ? async () => void (await pool.query("SELECT 1 FROM pipeline_state")) : undefined,
  logger: true,
});
app.log.info(`profiles come from ${source}; /sync ${queue ? "enabled" : "disabled"}`);

if (pool) {
  pool.on("error", (err) => app.log.error(err));
  app.addHook("onClose", async () => {
    await queue?.close();
    await pool.end();
  });
}
for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => void app.close());
}

await app.listen({ host: "0.0.0.0", port: 3000 });
