import { createServer } from "node:http";

// Placeholder: source A and the source B export are added with their connectors.
const server = createServer((req, res) => {
  const ok = req.url === "/health";
  res.writeHead(ok ? 200 : 404, { "content-type": "application/json" });
  res.end(JSON.stringify(ok ? { status: "ok" } : { error: "not found" }));
});
server.listen(4000);
for (const s of ["SIGINT", "SIGTERM"]) process.once(s, () => server.close());
