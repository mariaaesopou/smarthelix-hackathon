import { Queue, type JobsOptions } from "bullmq";
import type { Redis } from "ioredis";

export const QUEUE_NAMES = ["etl", "resolution", "ml"] as const;
export type QueueName = (typeof QUEUE_NAMES)[number];

/** Job payloads are ids and flags only, never data (they travel as CLI arguments). */
export interface EtlJobData {
  syncRunId: string;
  source: string;
  mode: "full" | "incremental";
}
export interface ResolutionJobData {
  syncRunId: string;
}
export interface MlJobData {
  batchId?: string;
}

/**
 * 3 attempts; waits come from the custom strategy in backoff.ts.
 * Failed jobs stay a day for inspection; completed ones are trimmed.
 * Producers must pass a UUID `jobId` (BullMQ 6.7.10 rejects integers and ids with ':').
 */
export const defaultJobOptions: JobsOptions = {
  attempts: 3,
  backoff: { type: "custom" },
  removeOnComplete: { age: 3600, count: 200 },
  removeOnFail: { age: 24 * 3600 },
};

export function makeQueue<T>(name: QueueName, connection: Redis): Queue<T> {
  return new Queue<T>(name, { connection, defaultJobOptions });
}
