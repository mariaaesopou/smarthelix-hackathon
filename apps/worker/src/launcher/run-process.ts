import { spawn } from "node:child_process";

// Exit codes the Python side promises (services/pipeline/src/pipeline/errors.py).
export const EXIT_OK = 0;
export const EXIT_RETRYABLE = 75;
export const EXIT_PERMANENT = 65;

export type Outcome =
  | { kind: "ok" }
  | { kind: "retryable"; reason: string }
  | { kind: "permanent"; reason: string };

export interface RunOptions {
  /** Kill the whole process group if the child runs longer than this. */
  timeoutMs: number;
  /** After SIGTERM, wait this long for a clean exit before SIGKILL. */
  killGraceMs?: number;
  env?: NodeJS.ProcessEnv;
  cwd?: string;
}

const TAIL_BYTES = 4096;

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
    let hardKill: NodeJS.Timeout | undefined;

    const killGroup = (signal: NodeJS.Signals) => {
      try {
        process.kill(-child.pid!, signal);
      } catch {
        // Group already gone: nothing left to kill.
      }
    };

    const timer = setTimeout(() => {
      timedOut = true;
      killGroup("SIGTERM"); // polite: lets Spark shut its JVM down
      hardKill = setTimeout(() => killGroup("SIGKILL"), killGraceMs);
    }, opts.timeoutMs);

    child.once("error", (err) => {
      clearTimeout(timer);
      clearTimeout(hardKill);
      reject(err);
    });

    // "close" (not "exit") fires after stdio is drained, so stderrTail is complete.
    child.once("close", (code, signal) => {
      clearTimeout(timer);
      clearTimeout(hardKill);
      killGroup("SIGKILL"); // sweep any grandchild that outlived its parent

      if (timedOut) {
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
        resolve({ kind: "retryable", reason: stderrTail.trim() || `exit ${code}` });
      }
    });
  });
}
