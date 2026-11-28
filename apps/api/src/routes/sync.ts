import type { FastifyInstance } from "fastify";
import { createSyncController } from "../controllers/sync.ts";
import type { SyncService } from "../services/sync.ts";

const errorResponse = { $ref: "error.json#" } as const;

const startSchema = {
  summary: "Start importing a source; the worker runs its connector",
  params: {
    type: "object",
    required: ["source"],
    properties: { source: { type: "string", minLength: 1, maxLength: 100 } },
  },
  querystring: {
    type: "object",
    properties: {
      mode: { type: "string", enum: ["full", "incremental"], default: "incremental" },
    },
  },
  response: {
    202: { $ref: "sync-run.json#" },
    400: errorResponse,
    404: errorResponse,
    409: errorResponse,
    422: errorResponse,
    503: errorResponse,
  },
} as const;

const getRunSchema = {
  summary: "Progress of one sync run",
  params: {
    type: "object",
    required: ["id"],
    properties: { id: { type: "string", format: "uuid" } },
  },
  response: { 200: { $ref: "sync-run.json#" }, 400: errorResponse, 404: errorResponse },
} as const;

export function syncRoutes(service: SyncService) {
  const controller = createSyncController(service);
  return async function register(app: FastifyInstance) {
    app.post("/sync/:source", { schema: startSchema }, controller.start);
    app.get("/sync/runs/:id", { schema: getRunSchema }, controller.getRun);
  };
}
