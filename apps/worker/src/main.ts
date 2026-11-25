import { Redis } from "ioredis";

// Day 2: connectivity only. Queue consumers arrive on Day 5.
const url = process.env.REDIS_URL;
if (!url) throw new Error("REDIS_URL is not set");

const redis = new Redis(url, { maxRetriesPerRequest: null });
redis.on("error", (err: Error) => console.error("redis error", err.message));
await redis.ping();
console.log("worker connected to redis; no consumers registered yet");

for (const signal of ["SIGINT", "SIGTERM"] as const) {
  process.once(signal, () => void redis.quit());
}
