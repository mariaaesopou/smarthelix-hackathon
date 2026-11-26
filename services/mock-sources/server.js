// Mock external sources for the connectors (no dependencies).
//
//   Source A  /a/profiles          REST/JSON, SMEs and startups, paging + updated_since
//   Source B  /b/export.json       freelancer export, different field names
//             /b/export.csv        same data as CSV (list fields joined with "|")
//
// Data comes from fixtures/*.json, written by benchmarks/generate/generate_seed_profiles.py.
// Set MOCK_RATE_LIMIT_PER_MIN (default 0 = off) to get 429 + Retry-After, so the
// queue's rate-limit handling can be tested.
import { createServer } from "node:http";
import { readFileSync } from "node:fs";

const PORT = Number(process.env.PORT ?? 4000);
const RATE_LIMIT = Number(process.env.MOCK_RATE_LIMIT_PER_MIN ?? 0);
const MAX_PER_PAGE = 100;
const DEFAULT_PER_PAGE = 50;

function load(name) {
  try {
    return JSON.parse(readFileSync(new URL(`./fixtures/${name}.json`, import.meta.url), "utf8"));
  } catch (err) {
    console.error(`cannot read fixtures/${name}.json (${err.message})`);
    console.error("generate it with: py benchmarks/generate/generate_seed_profiles.py");
    process.exit(1);
  }
}
const sourceA = load("source_a"); // sorted by last_modified, oldest first
const sourceB = load("source_b");
const byId = new Map(sourceA.map((r) => [r.id, r]));

const json = (res, status, body, headers = {}) => {
  res.writeHead(status, { "content-type": "application/json; charset=utf-8", ...headers });
  res.end(JSON.stringify(body));
};
const fail = (res, status, error, headers) => json(res, status, { error }, headers);

// ---- rate limit: fixed one-minute window, shared by all clients ----
let windowStart = Date.now();
let count = 0;
function limited() {
  if (!RATE_LIMIT) return 0;
  const now = Date.now();
  if (now - windowStart >= 60_000) [windowStart, count] = [now, 0];
  if (++count <= RATE_LIMIT) return 0;
  return Math.max(1, Math.ceil((windowStart + 60_000 - now) / 1000));
}

function intParam(params, name, fallback, min, max) {
  const raw = params.get(name);
  if (raw === null) return fallback;
  const n = Number(raw);
  if (!Number.isInteger(n) || n < min || n > max) return null;
  return n;
}

function listA(params, res) {
  const page = intParam(params, "page", 1, 1, 1_000_000);
  const perPage = intParam(params, "per_page", DEFAULT_PER_PAGE, 1, MAX_PER_PAGE);
  if (page === null) return fail(res, 400, "page must be an integer >= 1");
  if (perPage === null) return fail(res, 400, `per_page must be an integer 1-${MAX_PER_PAGE}`);

  let rows = sourceA;
  const since = params.get("updated_since");
  if (since !== null) {
    const t = Date.parse(since);
    if (Number.isNaN(t)) return fail(res, 400, "updated_since must be an ISO 8601 date or datetime");
    rows = rows.filter((r) => Date.parse(r.last_modified) >= t); // >= : callers overlap on purpose
  }
  const total = rows.length;
  const data = rows.slice((page - 1) * perPage, page * perPage);
  json(res, 200, {
    data, page, per_page: perPage, total,
    total_pages: Math.ceil(total / perPage),
    next_page: page * perPage < total ? page + 1 : null,
  });
}

// ---- source B as CSV ----
const B_COLUMNS = ["ref", "fullName", "bio", "field", "area", "expertise", "offers", "seeking",
  "speaks", "homepage", "profileLink", "modifiedAt", "hourlyRate", "availability"];
const csvCell = (v) => {
  const s = Array.isArray(v) ? v.join("|") : v === null || v === undefined ? "" : String(v);
  return /[",\r\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s;
};
const bCsv = [B_COLUMNS.join(","), ...sourceB.map((r) => B_COLUMNS.map((c) => csvCell(r[c])).join(","))]
  .join("\r\n") + "\r\n";

const server = createServer((req, res) => {
  const url = new URL(req.url ?? "/", "http://mock");
  const path = url.pathname.replace(/\/+$/, "") || "/";

  if (req.method !== "GET") return fail(res, 405, "method not allowed", { allow: "GET" });
  if (path === "/health") return json(res, 200, { status: "ok" });

  const wait = limited();
  if (wait) return fail(res, 429, "rate limit exceeded", { "retry-after": String(wait) });

  if (path === "/a") {
    return json(res, 200, { source: "A", total: sourceA.length, endpoints: ["/a/profiles", "/a/profiles/{id}"],
      params: { page: "from 1", per_page: `1-${MAX_PER_PAGE}, default ${DEFAULT_PER_PAGE}`, updated_since: "ISO 8601" } });
  }
  if (path === "/a/profiles") return listA(url.searchParams, res);
  if (path.startsWith("/a/profiles/")) {
    const rec = byId.get(decodeURIComponent(path.slice("/a/profiles/".length)));
    return rec ? json(res, 200, rec) : fail(res, 404, "not found");
  }

  if (path === "/b") {
    return json(res, 200, { source: "B", total: sourceB.length, endpoints: ["/b/export.json", "/b/export.csv"],
      note: "full export only, no filtering" });
  }
  if (path === "/b/export.json") return json(res, 200, sourceB);
  if (path === "/b/export.csv") {
    res.writeHead(200, { "content-type": "text/csv; charset=utf-8" });
    return res.end(bCsv);
  }

  fail(res, 404, "not found");
});

server.listen(PORT, () => {
  console.log(`mock-sources on :${PORT}  A=${sourceA.length} records  B=${sourceB.length} records` +
    (RATE_LIMIT ? `  rate limit ${RATE_LIMIT}/min` : ""));
});
for (const s of ["SIGINT", "SIGTERM"]) process.once(s, () => server.close());
