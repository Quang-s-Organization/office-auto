import { execSync, spawnSync, type SpawnSyncReturns } from "node:child_process";

export interface OfficeCLIResult {
  success: boolean;
  data: any;
  error?: string;
}

export function parseOfficeCLI(result: SpawnSyncReturns<string>): OfficeCLIResult {
  return parseOfficeCLIOutput(result.stdout ?? "", result.stderr ?? "", result.status ?? -1);
}

export function parseOfficeCLIOutput(stdout: string, stderr: string, status: number): OfficeCLIResult {
  if (status !== 0 && !stdout) {
    return {
      success: false,
      data: null,
      error: stderr.slice(0, 500) || "officecli command failed with no output",
    };
  }
  try {
    const raw = JSON.parse(stdout || "{}");
    // Normalize: different commands return different top-level shapes
    // validate → { ok, issues }, query → { data/results }, batch → { success, results }
    const success = raw.ok ?? raw.success ?? (status === 0);
    return {
      success,
      data: raw.data ?? raw,
      error: raw.error,
    };
  } catch {
    return {
      success: false,
      data: null,
      error: `Parse error: ${stdout.slice(0, 200) || stderr.slice(0, 200)}`,
    };
  }
}

export function officecli(args: string[]): OfficeCLIResult {
  const result = spawnSync("officecli", args.concat("--json"), {
    encoding: "utf-8",
    maxBuffer: 50 * 1024 * 1024,
    timeout: 120_000,
  });
  return parseOfficeCLI(result);
}

export function officecliRaw(args: string[]): string {
  return execSync(["officecli", ...args].join(" "), {
    encoding: "utf-8",
    maxBuffer: 50 * 1024 * 1024,
    timeout: 120_000,
  });
}

export function officecliBatch(
  file: string,
  batchInput: object[],
  opts: { stopOnError?: boolean } = {}
): OfficeCLIResult {
  const input = JSON.stringify(batchInput);
  const args = ["batch", file];
  if (opts.stopOnError !== false) args.push("--stop-on-error");
  args.push("--json");

  const result = spawnSync("officecli", args, {
    encoding: "utf-8",
    input,
    maxBuffer: 50 * 1024 * 1024,
    timeout: 300_000,
  });
  return parseOfficeCLI(result);
}
