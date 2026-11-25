import { readdir, readFile, writeFile } from "node:fs/promises";
import { compile } from "json-schema-to-typescript";

const dir = new URL("../schemas/", import.meta.url);
let out = "// Generated from schemas/. Do not edit; run pnpm generate.\n";
for (const file of (await readdir(dir)).sort()) {
  const schema = JSON.parse(await readFile(new URL(file, dir), "utf8"));
  out += "\n" + (await compile(schema, schema.title, { bannerComment: "" }));
}
await writeFile(new URL("../generated/index.ts", import.meta.url), out);
