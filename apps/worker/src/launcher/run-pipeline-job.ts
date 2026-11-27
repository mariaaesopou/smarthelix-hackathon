import { runProcess, type Outcome, type RunOptions } from "./run-process.js";

/** `python -m pipeline <job> <args...>`; the interpreter path comes from the image. */
export function runPipelineJob(job: string, args: string[], opts: RunOptions): Promise<Outcome> {
  const python = process.env.PYTHON_BIN ?? "python3";
  return runProcess(python, ["-m", "pipeline", job, ...args], opts);
}
