import { Worker, type Job, type WorkerOptions } from "bullmq";
import type { Redis } from "ioredis";
import { runPipelineJob } from "../launcher/run-pipeline-job.js";
import { throwUnlessOk } from "../launcher/to-queue-error.js";
import { makeBackoffStrategy, backoffConfigFromEnv } from "../queues/backoff.js";
import type { EtlJobData, MlJobData } from "../queues/index.js";

const MINUTE = 60_000;

/** Spawns `python -m pipeline <job> ...` and maps its exit code onto BullMQ behaviour. */
async function runJob(job: string, args: string[], timeoutMs: number, signal?: AbortSignal): Promise<void> {
  throwUnlessOk(await runPipelineJob(job, args, { timeoutMs, signal }));
}

export const processEtl = (job: Job<EtlJobData>, _token?: string, signal?: AbortSignal) =>
  runJob("etl", etlArgs(job.data), 10 * MINUTE, signal);

/** Pass the API's sync_runs id along so the connector continues that row, not a second one. */
export function etlArgs(data: EtlJobData): string[] {
  return [
    "--source", data.source,
    "--mode", data.mode,
    ...(data.syncRunId ? ["--sync-run-id", data.syncRunId] : []),
  ];
}

export const processMl = (job: Job<MlJobData>, _token?: string, signal?: AbortSignal) =>
  runJob("similarity", job.data.batchId ? ["--batch-id", job.data.batchId] : [], 30 * MINUTE, signal);

/**
 * etl: parallel (sources are independent; the DB allows one active run per source).
 * ml: one at a time on one replica. A Spark run is long, so the lock is 120 s and the
 * stalled check 60 s; one stall is tolerated, then the job fails (rule 13).
 *
 * The resolution queue has no consumer yet: today `etl` resolves inline, and the
 * separate `pipeline resolution` job arrives on Day 6 with the etl_done hand-off (rule 9).
 */
export function startWorkers(connection: Redis, env: NodeJS.ProcessEnv = process.env): Worker[] {
  const settings = { backoffStrategy: makeBackoffStrategy(backoffConfigFromEnv(env)) };
  const base: Pick<WorkerOptions, "connection" | "settings"> = { connection, settings };

  return [
    new Worker<EtlJobData>("etl", processEtl, { ...base, concurrency: 2 }),
    new Worker<MlJobData>("ml", processMl, {
      ...base,
      concurrency: 1,
      lockDuration: 120_000,
      stalledInterval: 60_000,
      maxStalledCount: 1,
    }),
  ];
}
