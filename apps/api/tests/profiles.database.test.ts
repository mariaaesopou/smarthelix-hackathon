import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import type { ProfilePage, Recommendation } from "@smarthelix/shared/generated";
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

  describe("recommendations from the current ML runs", () => {
    // Targets: other (live), mergedIntoOther -> other, mergedIntoLive -> the subject itself.
    const rec = {
      other: "f0000000-0000-4000-8000-000000000011",
      mergedIntoOther: "f0000000-0000-4000-8000-000000000012",
      mergedIntoLive: "f0000000-0000-4000-8000-000000000013",
      batch: "f0000000-0000-4000-8000-0000000000b1",
      similarRun: "f0000000-0000-4000-8000-0000000000c1",
      matchingRun: "f0000000-0000-4000-8000-0000000000c2",
      record: "f0000000-0000-4000-8000-0000000000a2",
    };

    before(async () => {
      await client.query(
        `INSERT INTO profiles (id, type, name) VALUES
           ($1, 'freelancer', 'Zzqtest Other'), ($2, 'freelancer', 'Zzqtest Old'),
           ($3, 'freelancer', 'Zzqtest Older')`,
        [rec.other, rec.mergedIntoOther, rec.mergedIntoLive]);
      // A card needs at least one source (profile-card.json).
      await client.query(
        `INSERT INTO source_records (id, source, source_id, raw, hash, original_url)
         VALUES ($1, 'source_a', 'zzqtest-2', '{}', 'h', 'https://example.org/a/zzqtest-2')`, [rec.record]);
      await client.query("INSERT INTO profile_sources VALUES ($1, $2, 'new', 1)", [rec.record, rec.other]);
      await client.query("UPDATE profiles SET merged_into = $1 WHERE id = $2", [rec.other, rec.mergedIntoOther]);
      await client.query("UPDATE profiles SET merged_into = $1 WHERE id = $2", [ids.live, rec.mergedIntoLive]);
      await client.query(
        "INSERT INTO ml_batches (id, data_version, status) VALUES ($1, 0, 'succeeded')", [rec.batch]);
      await client.query(
        `INSERT INTO ml_runs (id, batch_id, kind, data_version, status) VALUES
           ($1, $3, 'similarity', 0, 'succeeded'), ($2, $3, 'matching', 0, 'succeeded')`,
        [rec.similarRun, rec.matchingRun, rec.batch]);
      // Ranks: 1 merged into "other", 2 "other" again, 3 deleted, 4 merged into the subject.
      await client.query(
        `INSERT INTO similar_profiles (run_id, profile_id, similar_id, rank, score) VALUES
           ($1, $2, $3, 1, 0.9), ($1, $2, $4, 2, 0.8), ($1, $2, $5, 3, 0.7), ($1, $2, $6, 4, 0.6)`,
        [rec.similarRun, ids.live, rec.mergedIntoOther, rec.other, ids.deleted, rec.mergedIntoLive]);
      await client.query(
        `INSERT INTO potential_partners (run_id, profile_id, partner_id, rank, score, reasons) VALUES
           ($1, $2, $3, 1, 1, '{"matched_needs": ["web development"]}')`,
        [rec.matchingRun, ids.live, rec.other]);
      await client.query(
        `INSERT INTO ml_current (kind, run_id) VALUES ('similarity', $1), ('matching', $2)
         ON CONFLICT (kind) DO UPDATE SET run_id = EXCLUDED.run_id`,
        [rec.similarRun, rec.matchingRun]);
    });

    const list = async (url: string) => {
      const res = await app.inject(url);
      assert.equal(res.statusCode, 200, res.body);
      const items = res.json<Recommendation[]>();
      for (const item of items) assertMatches("recommendation.json", item);
      return items;
    };

    test("similar follows rule 21 on the real SQL", async () => {
      const items = await list(`/profiles/${ids.live}/similar`);
      // Only "other" survives: at the best rank of its two rows, renumbered to 1.
      assert.deepEqual(items.map((r) => [r.rank, r.profile.id, r.score]), [[1, rec.other, 0.9]]);
      assert.deepEqual(items[0].matched_needs, []);
    });

    test("partners carry their matched needs", async () => {
      const items = await list(`/profiles/${ids.live}/partners`);
      assert.deepEqual(items.map((r) => [r.profile.id, r.matched_needs]), [[rec.other, ["web development"]]]);
    });

    test("a profile without rows gets an empty list", async () => {
      assert.deepEqual(await list(`/profiles/${rec.other}/similar`), []);
    });

    test("307 for a merged subject, 404 for a deleted one", async () => {
      const merged = await app.inject(`/profiles/${rec.mergedIntoLive}/similar`);
      assert.equal(merged.statusCode, 307);
      assert.equal(merged.headers.location, `../${ids.live}/similar`);
      assert.equal((await app.inject(`/profiles/${ids.deleted}/partners`)).statusCode, 404);
    });
  });
});
