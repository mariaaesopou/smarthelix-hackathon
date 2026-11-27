import assert from "node:assert/strict";
import { after, before, describe, test } from "node:test";
import type { ProfilePage } from "@smarthelix/shared/generated";
import { buildApp } from "../src/app.ts";
import data from "../src/repositories/fixtures/profiles.json" with { type: "json" };
import { createFixtureProfileRepository } from "../src/repositories/fixtureProfiles.ts";
import { assertMatches } from "./helpers.ts";

const BAKERY = "b0000000-0000-4000-8000-000000000001";
const WEB_STUDIO = "b0000000-0000-4000-8000-000000000003";
const MERGED = "b0000000-0000-4000-8000-0000000000ff";

describe("profiles API on fixtures", () => {
  let app: Awaited<ReturnType<typeof buildApp>>;
  before(async () => {
    app = await buildApp({ profiles: createFixtureProfileRepository() });
  });
  after(() => app.close());

  const page = async (url: string) => {
    const res = await app.inject(url);
    assert.equal(res.statusCode, 200, res.body);
    const body = res.json<ProfilePage>();
    assertMatches("profile-page.json", body);
    return body;
  };

  test("every fixture profile matches profile.json", () => {
    for (const profile of data.profiles) assertMatches("profile.json", profile);
  });

  test("lists profiles by name with defaults", async () => {
    const body = await page("/profiles");
    assert.equal(body.page, 1);
    assert.equal(body.per_page, 20);
    assert.equal(body.total, 4);
    assert.deepEqual(body.items.map((p) => p.name),
      ["AgroSense Demo", "Demo UX Designer", "Demo Web Studio", "Αρτοποιείο Παράδειγμα"]);
  });

  test("search ignores case and Greek accents", async () => {
    assert.deepEqual((await page("/profiles?q=ΣΧΕΔΙΑΣΜΟΣ")).items.map((p) => p.id), [WEB_STUDIO]);
    assert.deepEqual((await page("/profiles?q=ψωμι")).items.map((p) => p.id), [BAKERY]);
  });

  test("filters combine", async () => {
    const body = await page("/profiles?type=freelancer&region=Attica");
    assert.deepEqual(body.items.map((p) => p.id), [WEB_STUDIO]);
    assert.equal((await page("/profiles?source=source_b")).total, 2);
    assert.equal((await page("/profiles?skill=React")).total, 1);
  });

  test("pages", async () => {
    const second = await page("/profiles?per_page=3&page=2");
    assert.equal(second.items.length, 1);
    assert.equal(second.total, 4);
  });

  test("rejects bad query values with the error shape", async () => {
    for (const url of ["/profiles?per_page=101", "/profiles?page=0", "/profiles?type=company", "/profiles?page=60"]) {
      const res = await app.inject(url);
      assert.equal(res.statusCode, 400, url);
      assertMatches("error.json", res.json());
    }
  });

  test("returns one profile", async () => {
    const res = await app.inject(`/profiles/${BAKERY}`);
    assert.equal(res.statusCode, 200);
    assertMatches("profile.json", res.json());
    assert.equal(res.json().cluster.label, "food");
  });

  test("redirects a merged id to the survivor with 307 and a relative Location", async () => {
    const res = await app.inject(`/profiles/${MERGED}`);
    assert.equal(res.statusCode, 307);
    assert.equal(res.headers.location, WEB_STUDIO);
  });

  test("404 for an unknown id and 400 for a malformed one", async () => {
    const missing = await app.inject("/profiles/00000000-0000-4000-8000-000000000000");
    assert.equal(missing.statusCode, 404);
    assertMatches("error.json", missing.json());
    const bad = await app.inject("/profiles/not-a-uuid");
    assert.equal(bad.statusCode, 400);
    assertMatches("error.json", bad.json());
  });
});
