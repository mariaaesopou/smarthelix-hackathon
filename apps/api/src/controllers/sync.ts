import type { FastifyReply, FastifyRequest } from "fastify";
import type { SyncMode } from "../repositories/syncRuns.ts";
import type { SyncService } from "../services/sync.ts";

const error = (statusCode: number, error: string, message: string) => ({ statusCode, error, message });

type StartRequest = FastifyRequest<{ Params: { source: string }; Querystring: { mode: SyncMode } }>;

export function createSyncController(service: SyncService) {
  return {
    async start(request: StartRequest, reply: FastifyReply) {
      const { source } = request.params;
      const result = await service.start(source, request.query.mode);
      switch (result.kind) {
        case "started":
          // 202: accepted, the worker does the import; poll the Location for progress.
          return reply.code(202).header("location", `runs/${result.run.id}`).send(result.run);
        case "unknown_source":
          return reply.code(404).send(error(404, "Not Found", `Unknown source ${source}`));
        case "no_connector":
          return reply.code(422).send(error(422, "Unprocessable Entity", `Source ${source} has no connector yet`));
        case "already_active":
          return reply.code(409).send(error(409, "Conflict",
            `A sync of ${source} is already queued or running: ${result.runId}`));
        case "queue_unavailable":
          return reply.code(503).send(error(503, "Service Unavailable",
            `The job queue is unavailable; sync run ${result.run.id} was marked failed. Try again later.`));
      }
    },

    async getRun(request: FastifyRequest<{ Params: { id: string } }>, reply: FastifyReply) {
      const run = await service.findRun(request.params.id);
      return run ?? reply.code(404).send(error(404, "Not Found", "Sync run not found"));
    },
  };
}
