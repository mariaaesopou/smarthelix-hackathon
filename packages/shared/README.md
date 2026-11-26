# Shared schemas

JSON Schemas (draft 2020-12) that the API, the worker and the Spark jobs agree on.
Each file in `schemas/` has an example with the same name in `examples/`.

| Schema | Describes | Used by |
|---|---|---|
| `profile.json` | Full profile: `GET /profiles/{id}` | API, web |
| `profile-card.json` | Short profile in lists | API, web |
| `profile-page.json` | One page of results: `GET /profiles` | API, web |
| `recommendation.json` | One item of `GET /profiles/{id}/similar` and `/partners` | API, web |
| `sync-run.json` | An import run: `POST /sync/{source}` | API, web |
| `error.json` | Body of every API error | API, web |
| `source-a-record.json` | A profile as source A sends it | connector A, mock sources |
| `source-b-record.json` | A freelancer as source B exports it | connector B, mock sources |
| `normalized-record.json` | Connector output, before resolution | connectors, resolution |
| `similar-profile.json`, `potential-partner.json`, `cluster-assignment.json` | Rows the Spark jobs write | Spark jobs, API |
| `etl-job.json`, `resolution-job.json`, `ml-job.json` | Queue job payloads | API, worker |

## Rules

- `$id` is the file name. Refer to another schema with `"$ref": "profile-card.json"`.
- Objects use `"additionalProperties": false`; optional values are required and nullable.
- After editing a schema, update its example, then run `pnpm test` and
  `pnpm generate`, and commit the generated files.
- Never edit `generated/` (TypeScript) or `services/pipeline/src/pipeline/generated/`
  (Python) by hand.

`pnpm test` checks every example against its schema, and every record in
`services/mock-sources/fixtures/` against the source A and B schemas.
