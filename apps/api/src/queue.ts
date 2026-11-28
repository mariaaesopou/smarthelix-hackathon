import type { EtlJob } from "@smarthelix/shared/generated";
import { Queue, type JobsOptions } from "bullmq";
import { Redis } from "ioredis";

/** Where the API puts jobs. BullMQ in production; tests pass a fake. */
export interface JobQueue {
  /** Adds an etl job whose id is the sync_runs id (rule 8). Rejects when Redis is unavailable. */
  addEtl(job: EtlJob & { syncRunId: string }): Promise<void>;
  close(): Promise<void>;
}

/**
 * Must match defaultJobOptions in apps/worker/src/queues/index.ts (a test checks it):
 * 3 attempts, the worker's custom backoff, failed jobs kept a day.
 */
export const ETL_JOB_OPTIONS: JobsOptions = {
  attempts: 3,
  backoff: { type: "custom" },
  removeOnComplete: { age: 3600, count: 200 },
  removeOnFail: { age: 24 * 3600 },
};

export function createBullQueue(redisUrl: string): JobQueue {
  // A producer must fail fast: without an offline queue, add() rejects at once while
  // Redis is down, so POST /sync answers 503 instead of hanging.
  const connection = new Redis(redisUrl, { enableOfflineQueue: false, maxRetriesPerRequest: 1 });
  connection.on("error", () => undefined); // reported through the failing add() instead
  const etl = new Queue<EtlJob>("etl", { connection, defaultJobOptions: ETL_JOB_OPTIONS });

  return {
    async addEtl(job) {
      // jobId = the sync_runs UUID: BullMQ 6.7.10 rejects integer ids and ids with ':'.
      await etl.add("etl", job, { jobId: job.syncRunId });
    },
    async close() {
      await etl.close();
      await connection.quit().catch(() => undefined);
    },
  };
}
