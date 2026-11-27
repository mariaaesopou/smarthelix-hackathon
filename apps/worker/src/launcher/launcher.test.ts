import assert from "node:assert/strict";
import { readFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { UnrecoverableError } from "bullmq";
import { runPipelineJob } from "./run-pipeline-job.js";
import { runProcess } from "./run-process.js";
import { throwUnlessOk } from "./to-queue-error.js";

const opts = { timeoutMs: 20_000 };

test("exit 0 is ok", async () => {
  assert.deepEqual(await runPipelineJob("selftest", ["--outcome", "ok"], opts), { kind: "ok" });
});

test("exit 75 is retryable and carries the stderr text", async () => {
  const o = await runPipelineJob("selftest", ["--outcome", "retry"], opts);
  assert.equal(o.kind, "retryable");
  assert.match((o as { reason: string }).reason, /retryable failure/);
});

test("exit 65 is permanent", async () => {
  assert.equal((await runPipelineJob("selftest", ["--outcome", "permanent"], opts)).kind, "permanent");
});

test("an unexpected Python crash fails open as retryable", async () => {
  assert.equal((await runPipelineJob("selftest", ["--outcome", "crash"], opts)).kind, "retryable");
});

test("a timeout kills the child and is retryable", async () => {
  const t0 = Date.now();
  const o = await runPipelineJob("selftest", ["--sleep", "60"], { timeoutMs: 500, killGraceMs: 500 });
  assert.equal(o.kind, "retryable");
  assert.match((o as { reason: string }).reason, /timed out/);
  assert.ok(Date.now() - t0 < 5000, "must not wait for the 60 s sleep");
});

test("a timeout also kills grandchildren (the JVM-behind-Python case)", async () => {
  const pidFile = join(mkdtempSync(join(tmpdir(), "launcher-")), "pid");
  // The shell starts a grandchild `sleep`, records its pid, then waits on it.
  const o = await runProcess("sh", ["-c", `sleep 300 & echo $! > ${pidFile}; wait`], {
    timeoutMs: 500,
    killGraceMs: 500,
  });
  assert.equal(o.kind, "retryable");
  const pid = Number(readFileSync(pidFile, "utf8"));
  assert.throws(() => process.kill(pid, 0), { code: "ESRCH" }, "grandchild must be dead");
});

test("outcomes map to BullMQ behaviour", () => {
  throwUnlessOk({ kind: "ok" });
  assert.throws(() => throwUnlessOk({ kind: "permanent", reason: "x" }), UnrecoverableError);
  assert.throws(
    () => throwUnlessOk({ kind: "retryable", reason: "x" }),
    (e: unknown) => e instanceof Error && !(e instanceof UnrecoverableError),
  );
});
