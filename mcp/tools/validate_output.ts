import { spawnSync } from "child_process"

function run(args: string[]): string {
  const r = spawnSync("officecli", args, { encoding: "utf-8" })
  if (r.error) throw r.error
  if (r.status !== 0) throw new Error(`officecli ${args[0]} failed: ${r.stderr}`)
  return r.stdout
}

export function validateOutput(output_path: string): unknown {
  run(["open", output_path])
  const validateRaw = run(["validate", output_path])
  const issuesRaw = run([
    "view",
    output_path,
    "issues",
    "--json",
    "--type", "format",
  ])
  const outline = run(["view", output_path, "outline"])
  run(["close", output_path])

  let valid = false
  let issues: any[] = []
  try {
    const parsed = JSON.parse(issuesRaw)
    issues = Array.isArray(parsed) ? parsed : parsed.issues ?? []
    valid = issues.length === 0
  } catch {
    valid = !/error|fail|invalid/i.test(issuesRaw)
  }

  const result = {
    valid,
    issue_count: issues.length,
    issues,
    outline_preview: outline,
  }

  return result
}
