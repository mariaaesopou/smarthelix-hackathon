import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import type { EtlJob, SyncRun } from "@smarthelix/shared/generated";
import pg from "pg";
import { defaultJobOptions } from "../../worker/src/queues/index.ts";
import { buildApp } from "../src/app.ts";
import { ETL_JOB_OPTIONS, type JobQueue } from "../src/queue.ts";
import { createDbProfileRepository } from "../src/repositories/dbProfiles.ts";
import { createDbSyncRunRepository } from "../src/repositories/syncRuns.ts";
import { assertMatches } from "./helpers.ts";

// Same rules as the other database tests: an unreachable database fails, SKIP_DB_TESTS=1 skips.
const URL = process.env.TEST_DATABASE_URL
  ?? "postgres://smarthelix:smarthelix_dev@127.0.0.1:5432/smarthelix?sslmode=disable";
const skip = process.env.SKIP_DB_TESTS === "1" && "SKIP_DB_TESTS=1";

/** Records the jobs it is given; `down` makes it fail like Redis being unavailable. */
class FakeQueue implements JobQueue {
  jobs: EtlJob[] = [];
  down = false;
  async addEtl(job: EtlJob & { syncRunId: string }) {
    if (this.down) throw new Error("Connection is closed.");
    this.jobs.push(job);
  }
  async close() {}
}

test("the API's etl job options match the worker's", () => {
  assert.deepEqual(ETL_JOB_OPTIONS, defaultJobOptions);
});

describe("POST /sync/{source} and GET /sync/runs/{id}", { skip }, () => {
  const client = new pg.Client({ connectionString: URL });
  const queue = new FakeQueue();
  let app: Awaited<ReturnType<typeof buildApp>>;

  // One transaction, rolled back at the end: the database is left unchanged.
  before(async () => {
    try {
      await client.connect();
    } catch (err) {
      throw new Error(`database not reachable: start the stack or set SKIP_DB_TESTS=1. ${String(err)}`);
    }
    await client.query("BEGIN");
    // Earlier runs of source_a must not count as active inside this test.
    await client.query("UPDATE sync_runs SET status = 'failed' WHERE source = 'source_a'"
      + " AND status IN ('queued', 'etl_running')");
    app = await buildApp({
      profiles: createDbProfileRepository(client),
      sync: { runs: createDbSyncRunRepository(client), queue },
    });
  });

  after(async () => {
    await app?.close();
    await client.query("ROLLBACK").catch(() => undefined);
    await client.end();
  });

  const statusOf = async (id: string) =>
    (await client.query("SELECT status, error_code FROM sync_runs WHERE id = $1", [id])).rows[0];

  let firstId = "";

  test("202: inserts a queued row, then adds the job with the same id", async () => {
    const res = await app.inject({ method: "POST", url: "/sync/source_a?mode=full" });
    assert.equal(res.statusCode, 202, res.body);
    const run = res.json<SyncRun>();
    assertMatches("sync-run.json", run);
    assert.equal(run.source, "source_a");
    assert.equal(run.mode, "full");
    assert.equal(run.status, "queued");
    assert.equal(res.headers.location, `runs/${run.id}`);
    assert.deepEqual(queue.jobs.at(-1), { syncRunId: run.id, source: "source_a", mode: "full" });
    assertMatches("etl-job.json", queue.jobs.at(-1));
    assert.equal((await statusOf(run.id)).status, "queued");
    firstId = run.id;
  });

  test("409 while a run of the source is queued or running", async () => {
    const res = await app.inject({ method: "POST", url: "/sync/source_a" });
    assert.equal(res.statusCode, 409);
    assertMatches("error.json", res.json());
    assert.match(res.json().message, new RegExp(firstId));
    assert.equal(queue.jobs.length, 1);
  });

  test("GET /sync/runs/{id} shows the run's progress", async () => {
    await client.query(
      "UPDATE sync_runs SET status = 'resolved', counts = '{\"fetched\": 3}', finished_at = now() WHERE id = $1",
      [firstId]);
    const res = await app.inject(`/sync/runs/${firstId}`);
    assert.equal(res.statusCode, 200);
    const run = res.json<SyncRun>();
    assertMatches("sync-run.json", run);
    assert.equal(run.status, "resolved");
    assert.deepEqual(run.counts, { fetched: 3 });
  });

  test("503 when the queue is down; the row is failed, so the next sync can start", async () => {
    queue.down = true;
    const res = await app.inject({ method: "POST", url: "/sync/source_a" });
    queue.down = false;
    assert.equal(res.statusCode, 503);
    assertMatches("error.json", res.json());
    const failed = /sync run ([0-9a-f-]{36})/.exec(res.json().message)?.[1];
    assert.ok(failed);
    assert.deepEqual(await statusOf(failed), { status: "failed", error_code: "queue_unavailable" });

    const next = await app.inject({ method: "POST", url: "/sync/source_a" });
    assert.equal(next.statusCode, 202, next.body);
    assert.equal(next.json<SyncRun>().mode, "incremental"); // the default
  });

  test("404 unknown source, 422 source without a connector, 400 bad mode", async () => {
    const unknown = await app.inject({ method: "POST", url: "/sync/source_z" });
    assert.equal(unknown.statusCode, 404);
    // A source that exists in the database but is not in syncSources.
    await client.query("INSERT INTO sources (name, base_url) VALUES ('zz_noconn', 'http://zz.example')");
    const noConnector = await app.inject({ method: "POST", url: "/sync/zz_noconn" });
    assert.equal(noConnector.statusCode, 422);
    const badMode = await app.inject({ method: "POST", url: "/sync/source_a?mode=everything" });
    assert.equal(badMode.statusCode, 400);
    for (const res of [unknown, noConnector, badMode]) assertMatches("error.json", res.json());
  });

  test("source_b has a connector, so it can be synced too", async () => {
    await client.query("UPDATE sync_runs SET status = 'failed' WHERE source = 'source_b'"
      + " AND status IN ('queued', 'etl_running')");
    const res = await app.inject({ method: "POST", url: "/sync/source_b?mode=full" });
    assert.equal(res.statusCode, 202, res.body);
    assert.deepEqual(queue.jobs.at(-1), { syncRunId: res.json<SyncRun>().id, source: "source_b", mode: "full" });
  });

  test("GET /sync/runs/{id}: 404 unknown, 400 not a UUID", async () => {
    assert.equal((await app.inject("/sync/runs/00000000-0000-4000-8000-000000000000")).statusCode, 404);
    assert.equal((await app.inject("/sync/runs/nope")).statusCode, 400);
  });
});
