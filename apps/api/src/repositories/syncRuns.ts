import type { SyncRun } from "@smarthelix/shared/generated";
import type { Queryable } from "./dbProfiles.ts";

export type SyncMode = SyncRun["mode"];

export type CreateResult =
  | { kind: "created"; run: SyncRun }
  /** Another run of this source is queued or running (index sync_runs_one_active). */
  | { kind: "active"; runId: string };

export interface SyncRunRepository {
  sourceExists(source: string): Promise<boolean>;
  create(source: string, mode: SyncMode): Promise<CreateResult>;
  findById(id: string): Promise<SyncRun | null>;
  /** Marks a run that never reached the queue as failed, so it stops blocking its source. */
  markNotQueued(id: string, errorCode: string): Promise<void>;
}

const COLUMNS = "id, source, mode, status, counts, error_code, created_at, started_at, finished_at";

/** sync_runs through plain, parameterised SQL. */
export function createDbSyncRunRepository(db: Queryable): SyncRunRepository {
  return {
    async sourceExists(source) {
      const { rows } = await db.query("SELECT 1 FROM sources WHERE name = $1", [source]);
      return rows.length > 0;
    },

    async create(source, mode) {
      // status defaults to 'queued'; the database creates the id (rule 8: the row first).
      // The conflict target is the partial unique index sync_runs_one_active, so a second
      // active run of a source inserts nothing instead of raising an error.
      const { rows } = await db.query<SyncRun>(
        `INSERT INTO sync_runs (source, mode) VALUES ($1, $2)
         ON CONFLICT (source) WHERE status IN ('queued', 'etl_running') DO NOTHING
         RETURNING ${COLUMNS}`, [source, mode]);
      if (rows[0]) return { kind: "created", run: rows[0] };
      const active = await db.query<{ id: string }>(
        "SELECT id FROM sync_runs WHERE source = $1 AND status IN ('queued', 'etl_running')", [source]);
      return { kind: "active", runId: active.rows[0]?.id ?? "unknown" };
    },

    async findById(id) {
      const { rows } = await db.query<SyncRun>(`SELECT ${COLUMNS} FROM sync_runs WHERE id = $1`, [id]);
      return rows[0] ?? null;
    },

    async markNotQueued(id, errorCode) {
      await db.query(
        "UPDATE sync_runs SET status = 'failed', error_code = $2, finished_at = now()"
        + " WHERE id = $1 AND status = 'queued'", [id, errorCode]);
    },
  };
}
