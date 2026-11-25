import Fastify from "fastify";
import pg from "pg";

const pool = new pg.Pool({ connectionString: process.env.DATABASE_URL });
const app = Fastify({ logger: true });

pool.on("error", (err) => app.log.error(err));

app.get("/health", async () => {
  await pool.query("SELECT 1 FROM pipeline_state");
  return { status: "ok" };
});

app.addHook("onClose", () => pool.end());
for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => void app.close());
}

await app.listen({ host: "0.0.0.0", port: 3000 });
