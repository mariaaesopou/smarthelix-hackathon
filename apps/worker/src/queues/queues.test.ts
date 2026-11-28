import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { randomUUID } from "node:crypto";
import { test } from "node:test";
import { Queue, QueueEvents, Worker, type Job } from "bullmq";
import { Redis } from "ioredis";
import { EXIT_OK, EXIT_PERMANENT, EXIT_RETRYABLE, type Outcome } from "../launcher/run-process.js";
import { runPipelineJob } from "../launcher/run-pipeline-job.js";
import { throwUnlessOk } from "../launcher/to-queue-error.js";
import { makeBackoffStrategy } from "./backoff.js";
import { QUEUE_NAMES, defaultJobOptions } from "./index.js";
import { etlArgs } from "../consumers/index.js";

const constants = JSON.parse(readFileSync(new URL("../../../../packages/shared/constants.json", import.meta.url), "utf8"));

test("exit codes and queue names match packages/shared/constants.json", () => {
  assert.deepEqual(constants.exitCodes, { success: EXIT_OK, permanent: EXIT_PERMANENT, retryable: EXIT_RETRYABLE });
  assert.deepEqual([...QUEUE_NAMES], constants.queues);
});

// Everything below needs a real Redis: set REDIS_URL (docker compose up redis).
const REDIS_URL = process.env.REDIS_URL;
const redisTest = REDIS_URL ? test : test.skip;

interface SelfTestJob { args: string[] }

async function harness(baseMs: number) {
  const name = `test-${randomUUID()}`;
  const connection = new Redis(REDIS_URL!, { maxRetriesPerRequest: null });
  const queue = new Queue<SelfTestJob>(name, { connection, defaultJobOptions });
  const eventsConnection = new Redis(REDIS_URL!, { maxRetriesPerRequest: null });
  const events = new QueueEvents(name, { connection: eventsConnection });
  await events.waitUntilReady();
  const starts: number[] = [];
  const ends: number[] = [];
  const outcomes: Outcome[] = [];
  const process = async (job: Job<SelfTestJob>, _t?: string, signal?: AbortSignal) => {
    starts.push(Date.now());
    const outcome = await runPipelineJob("selftest", job.data.args, { timeoutMs: 20_000, signal });
    outcomes.push(outcome);
    ends.push(Date.now());
    throwUnlessOk(outcome);
  };
  const worker = new Worker<SelfTestJob>(name, process, {
    connection,
    settings: { backoffStrategy: makeBackoffStrategy({ baseMs, maxMs: baseMs * 16, maxRetryAfterMs: 60_000, random: () => 0 }) },
  });
  const close = async () => {
    await worker.close(true);
    await events.close();
    await queue.obliterate({ force: true });
    await queue.close();
    connection.disconnect();
    eventsConnection.disconnect();
  };
  return { queue, events, worker, starts, ends, outcomes, close };
}

redisTest("a Retry-After hint delays the retry by at least that long", async () => {
  const h = await harness(100);
  try {
    // Succeeds on the retry only if the first try fails: selftest always fails, so cap attempts at 2.
    const job = await h.queue.add("x", { args: ["--outcome", "retry", "--retry-after", "1.5"] }, { jobId: randomUUID(), attempts: 2 });
    await assert.rejects(job.waitUntilFinished(h.events, 30_000));
    assert.equal(h.starts.length, 2);
    assert.ok(h.starts[1] - h.ends[0] >= 1500, `gap was ${h.starts[1] - h.ends[0]} ms`);
  } finally {
    await h.close();
  }
});

redisTest("without a hint the wait follows the exponential base", async () => {
  const h = await harness(800); // random=0 -> attempt 1 waits base/2 = 400 ms
  try {
    const job = await h.queue.add("x", { args: ["--outcome", "retry"] }, { jobId: randomUUID(), attempts: 2 });
    await assert.rejects(job.waitUntilFinished(h.events, 30_000));
    const gap = h.starts[1] - h.ends[0];
    assert.ok(gap >= 400 && gap < 1500, `gap was ${gap} ms`);
  } finally {
    await h.close();
  }
});

redisTest("a permanent failure is not retried", async () => {
  const h = await harness(100);
  try {
    const job = await h.queue.add("x", { args: ["--outcome", "permanent"] }, { jobId: randomUUID() });
    await assert.rejects(job.waitUntilFinished(h.events, 30_000));
    assert.equal(h.starts.length, 1);
  } finally {
    await h.close();
  }
});

redisTest("cancelling then closing the worker stops the running child process", async () => {
  const h = await harness(100);
  try {
    await h.queue.add("x", { args: ["--outcome", "ok", "--sleep", "60"] }, { jobId: randomUUID() });
    while (h.starts.length === 0) await new Promise((r) => setTimeout(r, 50));
    const t0 = Date.now();
    h.worker.cancelAllJobs("test shutdown");
    await h.worker.close();
    while (h.outcomes.length === 0 && Date.now() - t0 < 15_000) await new Promise((r) => setTimeout(r, 50));
    assert.equal(h.outcomes.length, 1, "the child was never stopped");
    assert.match((h.outcomes[0] as { reason: string }).reason, /aborted/);
    assert.ok(Date.now() - t0 < 10_000, "it took the full 60 s sleep to end");
  } finally {
    await h.close();
  }
});

test("etlArgs passes the API's syncRunId on, and omits it when absent", () => {
  const id = randomUUID();
  assert.deepEqual(etlArgs({ syncRunId: id, source: "source_a", mode: "full" }),
    ["--source", "source_a", "--mode", "full", "--sync-run-id", id]);
  assert.deepEqual(etlArgs({ syncRunId: "", source: "source_a", mode: "incremental" }),
    ["--source", "source_a", "--mode", "incremental"]);
});

test("the --sync-run-id flag reaches the Python CLI", async () => {
  // A malformed id is rejected by argparse (exit 65) before any database access, and the
  // message names the flag: proof the CLI received and parsed it.
  const o = await runPipelineJob("etl", etlArgs({ syncRunId: "not-a-uuid", source: "source_a", mode: "full" }), { timeoutMs: 20_000 });
  assert.equal(o.kind, "permanent");
  assert.match((o as { reason: string }).reason, /sync-run-id/);
});
