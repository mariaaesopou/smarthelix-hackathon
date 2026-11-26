import { readdir, readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { compile } from "json-schema-to-typescript";

const dir = new URL("../schemas/", import.meta.url);
let out = "// Generated from schemas/. Do not edit; run pnpm generate.\n";
for (const file of (await readdir(dir)).sort()) {
  const schema = JSON.parse(await readFile(new URL(file, dir), "utf8"));
  // cwd resolves "$ref": "other.json"; each referenced type is emitted by its own file.
  out += "\n" + (await compile(schema, schema.title, {
    bannerComment: "",
    cwd: fileURLToPath(dir),
    declareExternallyReferenced: false,
  }));
}
await writeFile(new URL("../generated/index.ts", import.meta.url), out);
