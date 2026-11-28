import type { BackoffStrategy } from "bullmq";

/** A retryable failure, optionally carrying the source's own Retry-After hint. */
export class RetryAfterError extends Error {
  constructor(
    message: string,
    readonly retryAfterMs?: number,
  ) {
    super(message);
    this.name = "RetryAfterError";
  }
}

export interface BackoffConfig {
  /** Delay before the first retry; doubles each attempt. */
  baseMs: number;
  /** Upper bound for the computed delay (not for a source's Retry-After). */
  maxMs: number;
  /** Upper bound for a Retry-After hint, so a bad header cannot park a job for days. */
  maxRetryAfterMs: number;
  /** Random source in [0, 1); injectable for tests. */
  random?: () => number;
}

/** 30 s base for real runs; BACKOFF_BASE_MS=2000 keeps a live demo moving. */
export function backoffConfigFromEnv(env: NodeJS.ProcessEnv = process.env): BackoffConfig {
  const baseMs = Number(env.BACKOFF_BASE_MS ?? 30_000);
  if (!Number.isFinite(baseMs) || baseMs <= 0) throw new Error("BACKOFF_BASE_MS must be a positive number");
  return { baseMs, maxMs: baseMs * 16, maxRetryAfterMs: 15 * 60_000 };
}

/**
 * Exponential backoff with "equal jitter": half the delay is fixed, half is random.
 * attempt 1 -> 15-30 s, 2 -> 30-60 s, 3 -> 60-120 s (base 30 s). The fixed half keeps
 * a real wait; the random half stops jobs that failed together from retrying together.
 */
export function jitteredDelayMs(attemptsMade: number, cfg: BackoffConfig): number {
  const random = cfg.random ?? Math.random;
  const exp = Math.min(cfg.baseMs * 2 ** Math.max(attemptsMade - 1, 0), cfg.maxMs);
  return Math.round(exp / 2 + random() * (exp / 2));
}

/**
 * BullMQ backoff strategy. If the failure carried a Retry-After hint we wait at least
 * that long (plus a little jitter so retries spread out); otherwise jittered exponential.
 * Register as `settings: { backoffStrategy }` on the Worker and give jobs
 * `backoff: { type: "custom" }`.
 */
export function makeBackoffStrategy(cfg: BackoffConfig): BackoffStrategy {
  const random = cfg.random ?? Math.random;
  return (attemptsMade, _type, err) => {
    const hint = err instanceof RetryAfterError ? err.retryAfterMs : undefined;
    const computed = jitteredDelayMs(attemptsMade, cfg);
    if (hint === undefined) return computed;
    const wait = Math.min(hint, cfg.maxRetryAfterMs);
    // Never retry sooner than the source asked; add up to 10% so a burst spreads out.
    return Math.max(computed, wait + Math.round(random() * wait * 0.1));
  };
}
