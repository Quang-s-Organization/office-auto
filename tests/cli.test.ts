import { describe, it, expect } from 'vitest';
import { spawnSync } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const CLI_PATH = resolve(__dirname, '../../bin/office-auto-cli.ts');
const NODE_BIN = process.execPath;

function runCLI(args: string[]) {
  return spawnSync(NODE_BIN, ['--import', 'tsx', CLI_PATH, ...args], {
    encoding: 'utf-8',
    cwd: resolve(__dirname, '../..'),
    timeout: 30000,
  });
}

describe('office-auto CLI', () => {
  it('shows help when called without arguments', () => {
    const result = runCLI([]);
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('office-auto CLI');
    expect(result.stdout).toContain('Commands:');
    expect(result.stdout).toContain('generate');
    expect(result.stdout).toContain('inspect');
  });

  it('shows help with --help flag', () => {
    const result = runCLI(['--help']);
    expect(result.status).toBe(0);
    expect(result.stdout).toContain('office-auto CLI');
  });

  it('returns error code 2 for missing required arguments', () => {
    const result = runCLI(['generate']);
    expect(result.status).toBe(2);
    expect(result.stderr).toContain('--template, --source, and --target are required');
  });

  it('returns error code 2 for unknown command', () => {
    const result = runCLI(['unknown']);
    expect(result.status).toBe(2);
    expect(result.stderr).toContain('Unknown command: unknown');
  });

  it('returns error code 2 for inspect without --run-id', () => {
    const result = runCLI(['inspect']);
    expect(result.status).toBe(2);
    expect(result.stderr).toContain('--run-id is required');
  });

  it('attempts to run pipeline with valid arguments (may fail if files missing)', () => {
    const result = runCLI([
      'generate',
      '--template',
      '/tmp/nonexistent.docx',
      '--source',
      '/tmp/nonexistent.md',
      '--target',
      '/tmp/output.docx',
    ]);
    
    // Should exit with 1 (pipeline failure) or 3 (unexpected error)
    // because the files don't exist
    expect([1, 3]).toContain(result.status);
    expect(result.stdout).toContain('Starting pipeline...');
  });
});
