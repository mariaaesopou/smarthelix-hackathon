import assert from "node:assert/strict";
import { test } from "node:test";
import { RetryAfterError, backoffConfigFromEnv, jitteredDelayMs, makeBackoffStrategy } from "./backoff.js";
import { runPipelineJob } from "../launcher/run-pipeline-job.js";
import { parseRetryAfterMs } from "../launcher/run-process.js";

const cfg = (random: () => number) => ({ baseMs: 30_000, maxMs: 480_000, maxRetryAfterMs: 900_000, random });

test("delay doubles per attempt and stays inside the jitter band", () => {
  for (const [attempt, exp] of [[1, 30_000], [2, 60_000], [3, 120_000]] as const) {
    assert.equal(jitteredDelayMs(attempt, cfg(() => 0)), exp / 2);
    assert.equal(jitteredDelayMs(attempt, cfg(() => 0.999999)), Math.round(exp * 0.9999995));
  }
});

test("delay is capped", () => {
  assert.equal(jitteredDelayMs(20, cfg(() => 0)), 240_000);
});

test("without a hint, the strategy uses jittered exponential", () => {
  const s = makeBackoffStrategy(cfg(() => 0));
  assert.equal(s(2, "custom", new Error("boom")), 30_000);
});

test("Retry-After raises the wait above the computed delay", () => {
  const s = makeBackoffStrategy(cfg(() => 0));
  assert.equal(s(1, "custom", new RetryAfterError("429", 90_000)), 90_000);
});

test("a short Retry-After never lowers the computed delay", () => {
  const s = makeBackoffStrategy(cfg(() => 0));
  assert.equal(s(3, "custom", new RetryAfterError("429", 1_000)), 60_000);
});

test("an absurd Retry-After is capped", () => {
  const s = makeBackoffStrategy(cfg(() => 0));
  assert.equal(s(1, "custom", new RetryAfterError("429", 86_400_000)), 900_000);
});

test("BACKOFF_BASE_MS shortens the demo", () => {
  assert.equal(backoffConfigFromEnv({ BACKOFF_BASE_MS: "2000" }).baseMs, 2000);
  assert.equal(backoffConfigFromEnv({}).baseMs, 30_000);
  assert.throws(() => backoffConfigFromEnv({ BACKOFF_BASE_MS: "abc" }));
});

test("parseRetryAfterMs reads the last marker line", () => {
  assert.equal(parseRetryAfterMs("x\nretry-after-ms: 1500\n"), 1500);
  assert.equal(parseRetryAfterMs("nothing here"), undefined);
});

test("Python's Retry-After reaches the Outcome end to end", async () => {
  const o = await runPipelineJob("selftest", ["--outcome", "retry", "--retry-after", "2.5"], { timeoutMs: 20_000 });
  assert.equal(o.kind, "retryable");
  assert.equal((o as { retryAfterMs?: number }).retryAfterMs, 2500);
});
