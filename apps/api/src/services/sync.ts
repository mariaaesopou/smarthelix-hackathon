import type { SyncRun } from "@smarthelix/shared/generated";
import constants from "@smarthelix/shared/constants.json" with { type: "json" };
import type { JobQueue } from "../queue.ts";
import type { SyncMode, SyncRunRepository } from "../repositories/syncRuns.ts";

/** Sources with a connector. A source without one would leave its row queued forever. */
export const SYNC_SOURCES: readonly string[] = constants.syncSources;

export type StartResult =
  | { kind: "started"; run: SyncRun }
  | { kind: "unknown_source" }
  | { kind: "no_connector" }
  | { kind: "already_active"; runId: string }
  | { kind: "queue_unavailable"; run: SyncRun };

export interface SyncService {
  start(source: string, mode: SyncMode): Promise<StartResult>;
  findRun(id: string): Promise<SyncRun | null>;
}

export function createSyncService(runs: SyncRunRepository, queue: JobQueue): SyncService {
  return {
    /**
     * Rule 8: insert the sync_runs row, then add the job with that id. The worker's
     * connector continues the same row (--sync-run-id). If the job cannot be added,
     * the row is marked failed at once, so it does not block the source.
     */
    async start(source, mode) {
      if (!(await runs.sourceExists(source))) return { kind: "unknown_source" };
      if (!SYNC_SOURCES.includes(source)) return { kind: "no_connector" };

      const created = await runs.create(source, mode);
      if (created.kind === "active") return { kind: "already_active", runId: created.runId };

      try {
        await queue.addEtl({ syncRunId: created.run.id, source, mode });
      } catch {
        await runs.markNotQueued(created.run.id, "queue_unavailable");
        const failed = await runs.findById(created.run.id);
        return { kind: "queue_unavailable", run: failed ?? created.run };
      }
      return { kind: "started", run: created.run };
    },

    findRun: (id) => runs.findById(id),
  };
}
