import { execSync, spawnSync } from "node:child_process";

export interface OfficeCLIResult {
  success: boolean;
  data: any;
  error?: string;
}

export function officecli(args: string[]): OfficeCLIResult {
  const result = spawnSync("officecli", args.concat("--json"), {
    encoding: "utf-8",
    maxBuffer: 50 * 1024 * 1024,
    timeout: 120_000,
  });

  try {
    const parsed = JSON.parse(result.stdout || "{}");
    return parsed;
  } catch {
    return {
      success: false,
      data: null,
      error: `Parse error: ${result.stdout?.slice(0, 500) || result.stderr}`,
    };
  }
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
  const args = ["batch", file, "--stop-on-error"];
  if (opts.stopOnError !== false) args.push("--stop-on-error");
  args.push("--json");

  const result = spawnSync("officecli", args, {
    encoding: "utf-8",
    input,
    maxBuffer: 50 * 1024 * 1024,
    timeout: 300_000,
  });

  try {
    return JSON.parse(result.stdout || "{}");
  } catch {
    return {
      success: false,
      data: null,
      error: `Batch parse error: ${result.stdout?.slice(0, 500) || result.stderr}`,
    };
  }
}
