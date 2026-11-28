import { UnrecoverableError } from "bullmq";
import { RetryAfterError } from "../queues/backoff.js";
import type { Outcome } from "./run-process.js";

/**
 * Translate an Outcome into what a BullMQ processor must do.
 *   ok        -> return normally            -> job completed
 *   retryable -> throw a normal Error       -> BullMQ applies attempts + backoff
 *   permanent -> throw UnrecoverableError   -> job fails at once, no retries
 */
export function throwUnlessOk(outcome: Outcome): void {
  if (outcome.kind === "ok") return;
  if (outcome.kind === "permanent") throw new UnrecoverableError(outcome.reason);
  throw new RetryAfterError(outcome.reason, outcome.retryAfterMs);
}
