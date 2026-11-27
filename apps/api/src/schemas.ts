import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import type { FastifyInstance } from "fastify";

const SCHEMA_DIR = dirname(fileURLToPath(import.meta.resolve("@smarthelix/shared/schemas/profile.json")));

/**
 * Registers every schema of packages/shared under its $id, so routes can use
 * { $ref: "profile-page.json#" }. Fastify's validator is draft-07 and rejects the
 * 2020-12 "$schema" URI, so that one key is dropped; nothing else in our schemas
 * differs between the two drafts.
 */
export function registerSharedSchemas(app: FastifyInstance): void {
  for (const file of readdirSync(SCHEMA_DIR).filter((f) => f.endsWith(".json")).sort()) {
    const { $schema: _draft, ...schema } = JSON.parse(readFileSync(join(SCHEMA_DIR, file), "utf8"));
    app.addSchema(schema);
  }
}
