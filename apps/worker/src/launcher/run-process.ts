import { spawn } from "node:child_process";

// Exit codes the Python side promises (services/pipeline/src/pipeline/errors.py).
export const EXIT_OK = 0;
export const EXIT_RETRYABLE = 75;
export const EXIT_PERMANENT = 65;

export type Outcome =
  | { kind: "ok" }
  | { kind: "retryable"; reason: string; retryAfterMs?: number }
  | { kind: "permanent"; reason: string };

export interface RunOptions {
  /** Kill the whole process group if the child runs longer than this. */
  timeoutMs: number;
  /** After SIGTERM, wait this long for a clean exit before SIGKILL. */
  killGraceMs?: number;
  env?: NodeJS.ProcessEnv;
  cwd?: string;
  /** Aborting (worker shutdown, lost lock) stops the child the same way a timeout does. */
  signal?: AbortSignal;
}

const TAIL_BYTES = 4096;

/** The Python CLI ends stderr with `retry-after-ms: N` when a source sent Retry-After. */
export function parseRetryAfterMs(stderrTail: string): number | undefined {
  const matches = [...stderrTail.matchAll(/^retry-after-ms: (\d+)\s*$/gm)];
  const last = matches.at(-1);
  return last ? Number(last[1]) : undefined;
}

/**
 * Run a child process to completion and classify how it ended.
 *
 * Never throws for a failing child: the caller decides what an outcome means
 * (see to-queue-error.ts). Rejects only if the process cannot be started at all.
 */
export function runProcess(command: string, args: string[], opts: RunOptions): Promise<Outcome> {
  const killGraceMs = opts.killGraceMs ?? 5000;

  return new Promise((resolve, reject) => {
    // detached: true makes the child the leader of a NEW process group. Spark leaves a
    // JVM behind the Python process; signalling the group (negative pid) reaches both.
    const child = spawn(command, args, {
      detached: true,
      stdio: ["ignore", "pipe", "pipe"],
      env: opts.env ?? process.env,
      cwd: opts.cwd,
    });

    let stderrTail = "";
    child.stdout.on("data", (chunk: Buffer) => process.stdout.write(chunk));
    child.stderr.on("data", (chunk: Buffer) => {
      process.stderr.write(chunk);
      stderrTail = (stderrTail + chunk.toString()).slice(-TAIL_BYTES);
    });

    let timedOut = false;
    let aborted = false;
    let hardKill: NodeJS.Timeout | undefined;

    const killGroup = (signal: NodeJS.Signals) => {
      try {
        process.kill(-child.pid!, signal);
      } catch {
        // Group already gone: nothing left to kill.
      }
    };

    const stop = () => {
      killGroup("SIGTERM"); // polite: lets Spark shut its JVM down
      hardKill ??= setTimeout(() => killGroup("SIGKILL"), killGraceMs);
    };
    const timer = setTimeout(() => {
      timedOut = true;
      stop();
    }, opts.timeoutMs);
    const onAbort = () => {
      aborted = true;
      stop();
    };
    if (opts.signal?.aborted) onAbort();
    else opts.signal?.addEventListener("abort", onAbort, { once: true });

    child.once("error", (err) => {
      opts.signal?.removeEventListener("abort", onAbort);
      clearTimeout(timer);
      clearTimeout(hardKill);
      reject(err);
    });

    // "close" (not "exit") fires after stdio is drained, so stderrTail is complete.
    child.once("close", (code, signal) => {
      opts.signal?.removeEventListener("abort", onAbort);
      clearTimeout(timer);
      clearTimeout(hardKill);
      killGroup("SIGKILL"); // sweep any grandchild that outlived its parent

      if (aborted) {
        resolve({ kind: "retryable", reason: "aborted: worker is shutting down" });
      } else if (timedOut) {
        resolve({ kind: "retryable", reason: `timed out after ${opts.timeoutMs} ms` });
      } else if (code === EXIT_OK) {
        resolve({ kind: "ok" });
      } else if (code === EXIT_PERMANENT) {
        resolve({ kind: "permanent", reason: stderrTail.trim() || "exit 65" });
      } else if (code === null) {
        // Killed by a signal we did not send, e.g. the kernel OOM killer (SIGKILL).
        resolve({ kind: "retryable", reason: `killed by ${signal}` });
      } else {
        // 75, and any code we do not recognise, fail open like the Python side does.
        resolve({
          kind: "retryable",
          reason: stderrTail.trim() || `exit ${code}`,
          retryAfterMs: parseRetryAfterMs(stderrTail),
        });
      }
    });
  });
}
