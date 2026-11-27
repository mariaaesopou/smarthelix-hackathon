import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import type { ProfilePage } from "@smarthelix/shared/generated";
import pg from "pg";
import { buildApp } from "../src/app.ts";
import { createDbProfileRepository } from "../src/repositories/dbProfiles.ts";
import { assertMatches } from "./helpers.ts";

// The local compose database by default. Skipped when it is not reachable.
const URL = process.env.TEST_DATABASE_URL
  ?? "postgres://smarthelix:smarthelix_dev@127.0.0.1:5432/smarthelix?sslmode=disable";

const client = new pg.Client({ connectionString: URL });
const reachable = await client.connect().then(() => true, () => false);

describe("profiles API on the database", { skip: !reachable && "database not reachable" }, () => {
  let app: Awaited<ReturnType<typeof buildApp>>;
  const ids = {
    live: "f0000000-0000-4000-8000-000000000001",
    merged: "f0000000-0000-4000-8000-000000000002",
    deleted: "f0000000-0000-4000-8000-000000000003",
    record: "f0000000-0000-4000-8000-0000000000a1",
  };

  // Everything runs in one transaction that is rolled back, so the database is unchanged.
  before(async () => {
    await client.query("BEGIN");
    await client.query(
      `INSERT INTO sources (name, base_url) VALUES ('source_a', 'http://localhost:4000/a')
       ON CONFLICT DO NOTHING`);
    await client.query(
      `INSERT INTO profiles (id, type, name, description, sector, region, skills, services) VALUES
         ($1, 'sme', 'Zzqtest Ζαχαροπλαστείο', 'Γλυκά και τούρτες κατά παραγγελία', 'food', 'Epirus',
          '{pastry}', '{"γλυκά κατά παραγγελία"}'),
         ($2, 'sme', 'Zzqtest Merged', '', 'food', 'Epirus', '{}', '{}'),
         ($3, 'sme', 'Zzqtest Deleted', '', 'food', 'Epirus', '{}', '{}')`,
      [ids.live, ids.merged, ids.deleted]);
    await client.query("UPDATE profiles SET merged_into = $1 WHERE id = $2", [ids.live, ids.merged]);
    await client.query("UPDATE profiles SET deleted_at = now() WHERE id = $1", [ids.deleted]);
    await client.query(
      `INSERT INTO source_records (id, source, source_id, raw, hash, original_url)
       VALUES ($1, 'source_a', 'zzqtest-1', '{}', 'h', 'https://example.org/a/zzqtest-1')`, [ids.record]);
    await client.query(
      `INSERT INTO profile_sources VALUES ($1, $2, 'new', 1)`, [ids.record, ids.live]);
    app = await buildApp({ profiles: createDbProfileRepository(client) });
  });

  after(async () => {
    await app?.close();
    await client.query("ROLLBACK");
    await client.end();
  });

  const page = async (url: string) => {
    const res = await app.inject(url);
    assert.equal(res.statusCode, 200, res.body);
    const body = res.json<ProfilePage>();
    assertMatches("profile-page.json", body);
    return body;
  };

  test("finds a profile by Greek words, with or without accents and case", async () => {
    for (const q of ["τούρτες", "τουρτεσ", "ΤΟΥΡΤΕΣ"]) {
      const body = await page(`/profiles?q=${encodeURIComponent(q)}&region=Epirus`);
      assert.deepEqual(body.items.map((p) => p.id), [ids.live], q);
    }
  });

  test("matches a misspelt name", async () => {
    const body = await page("/profiles?q=Zzqtets");
    assert.ok(body.items.some((p) => p.id === ids.live));
  });

  test("never lists merged or deleted profiles", async () => {
    const body = await page("/profiles?q=Zzqtest&per_page=100");
    const found = body.items.map((p) => p.id);
    assert.ok(found.includes(ids.live));
    assert.ok(!found.includes(ids.merged));
    assert.ok(!found.includes(ids.deleted));
  });

  test("a card lists its sources", async () => {
    const body = await page("/profiles?q=Zzqtest&source=source_a");
    assert.deepEqual(body.items.find((p) => p.id === ids.live)?.sources, ["source_a"]);
  });

  test("total counts every page", async () => {
    const all = await page("/profiles?per_page=100");
    const next = await page("/profiles?per_page=100&page=2");
    assert.equal(all.total, next.total);
    assert.ok(all.items.every((p) => !next.items.some((q) => q.id === p.id)));
  });

  test("returns the full profile with its source link", async () => {
    const res = await app.inject(`/profiles/${ids.live}`);
    assert.equal(res.statusCode, 200);
    const body = res.json();
    assertMatches("profile.json", body);
    assert.deepEqual(body.sources, [{
      name: "source_a", url: "http://localhost:4000/a", original_url: "https://example.org/a/zzqtest-1",
    }]);
  });

  test("307 for a merged id, 404 for a deleted one", async () => {
    const merged = await app.inject(`/profiles/${ids.merged}`);
    assert.equal(merged.statusCode, 307);
    assert.equal(merged.headers.location, ids.live);
    const deleted = await app.inject(`/profiles/${ids.deleted}`);
    assert.equal(deleted.statusCode, 404);
    assertMatches("error.json", deleted.json());
  });
});
