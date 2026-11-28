import { Redis } from "ioredis";
import { startWorkers } from "./consumers/index.js";

const url = process.env.REDIS_URL;
if (!url) throw new Error("REDIS_URL is not set");

// BullMQ workers need blocking commands, so ioredis must not give up per request.
const connection = new Redis(url, { maxRetriesPerRequest: null });
connection.on("error", (err: Error) => console.error("redis error", err.message));
await connection.ping();

const workers = startWorkers(connection);
for (const w of workers) {
  w.on("failed", (job, err) => console.error(`${w.name} job ${job?.id} failed (attempt ${job?.attemptsMade}):`, err.message));
  w.on("error", (err) => console.error(`${w.name} worker error`, err.message));
}
console.log(`worker connected to redis; consuming: ${workers.map((w) => w.name).join(", ")}`);

let stopping = false;
async function shutdown(): Promise<void> {
  if (stopping) return;
  stopping = true;
  console.log("shutting down: stopping child processes and closing workers");
  // Close alone leaves running jobs (and their Python/JVM children) alone, so cancel first:
  // each processor's abort signal stops its process tree, the job fails as retryable
  // and is re-queued with backoff, and close() then returns once those have settled.
  for (const w of workers) w.cancelAllJobs("worker shutting down");
  await Promise.allSettled(workers.map((w) => w.close()));
  await connection.quit();
}
for (const signal of ["SIGINT", "SIGTERM"] as const) process.once(signal, () => void shutdown());
