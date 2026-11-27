import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020, type ValidateFunction } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const dir = dirname(fileURLToPath(import.meta.resolve("@smarthelix/shared/schemas/profile.json")));
const ajv = new Ajv2020({ strict: true, allowUnionTypes: true });
addFormats.default(ajv);
for (const file of readdirSync(dir).filter((f) => f.endsWith(".json"))) {
  ajv.addSchema(JSON.parse(readFileSync(join(dir, file), "utf8")));
}

/**
 * Validates a response body against a shared schema with the same strict 2020-12
 * validator as packages/shared, so the API cannot drift from the contract.
 */
export function assertMatches(schema: string, body: unknown): void {
  const validate = ajv.getSchema(schema) as ValidateFunction;
  if (!validate(body)) {
    throw new Error(`${schema}: ${ajv.errorsText(validate.errors)}\n${JSON.stringify(body).slice(0, 500)}`);
  }
}
