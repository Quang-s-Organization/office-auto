import { mkdirSync, writeFileSync } from "fs"
import { join } from "path"

export const RUN_DIR: string = (() => {
  const ts = new Date().toISOString().replace(/[:.]/g, "-")
  const dir = join(process.env.OFFICE_AUTO_WORKSPACE ?? process.cwd(), "runs", ts)
  mkdirSync(dir, { recursive: true })
  return dir
})()

export function logArtifact(name: string, data: unknown): string {
  const path = join(RUN_DIR, name)
  writeFileSync(path, JSON.stringify(data, null, 2), "utf-8")
  return path
}
