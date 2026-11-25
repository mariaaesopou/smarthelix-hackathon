import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import test from "node:test";
import { Ajv2020 } from "ajv/dist/2020.js";
import addFormats from "ajv-formats";

const read = (p) => JSON.parse(readFileSync(new URL(p, import.meta.url), "utf8"));
const ajv = new Ajv2020({ strict: true, allowUnionTypes: true });
addFormats.default(ajv);

for (const file of readdirSync(new URL("../schemas/", import.meta.url))) {
  test(file, () => {
    const validate = ajv.compile(read(`../schemas/${file}`));
    const example = read(`../examples/${file}`);
    assert.ok(validate(example), JSON.stringify(validate.errors));
    assert.equal(validate({ ...example, unexpected: 1 }), false);
  });
}
