import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";
import { Ajv2020 } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const ajv = new Ajv2020({ strict: true, allowUnionTypes: true });
addFormats.default(ajv);

// Register every schema first, so "$ref": "profile-card.json" resolves by $id.
const files = readdirSync(new URL("../schemas/", import.meta.url));
for (const file of files) {
  const schema = read(`../schemas/${file}`);
  assert.equal(schema.$id, file, `${file}: $id must equal the file name`);
  ajv.addSchema(schema);
}

for (const file of files) {
  test(file, () => {
    const validate = ajv.getSchema(file);
    const example = read(`../examples/${file}`);
    assert.ok(validate(example), JSON.stringify(validate.errors));
    assert.equal(validate({ ...example, unexpected: 1 }), false);
  });
}

// The mock sources must keep to the schemas the connectors rely on.
for (const [fixture, schema] of [
  ["source_a", "source-a-record.json"],
  ["source_b", "source-b-record.json"],
]) {
  test(`mock-sources fixture ${fixture}`, () => {
    const validate = ajv.getSchema(schema);
    const records = read(`../../../services/mock-sources/fixtures/${fixture}.json`);
    assert.ok(records.length > 0);
    for (const record of records) {
      assert.ok(validate(record), `${record.id ?? record.ref}: ${JSON.stringify(validate.errors)}`);
    }
  });
}
