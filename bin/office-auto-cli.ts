#!/usr/bin/env node

/**
 * office-auto CLI - Ground truth for document generation
 * 
 * This CLI runs the pipeline directly without LLM or MCP.
 * If this fails, DO NOT touch the agent - fix the core first.
 * 
 * Usage:
 *   office-auto generate --template <path> --source <path> --target <path>
 *   office-auto inspect --run-id <id>
 */

import { parseArgs } from 'node:util';
import { runPipeline } from '../mcp/orchestration/pipeline-supervisor.js';
import { readRunState, getRunDir } from '../mcp/lib/artifact-store.js';

function printUsage() {
  console.log(`
office-auto CLI - Deterministic document generation

Commands:
  generate    Generate a document from template + source
  inspect     Inspect a run's state and artifacts

Usage:
  office-auto generate --template <path> --source <path> --target <path>
  office-auto inspect --run-id <id>

Examples:
  office-auto generate --template ./format_template.docx --source ./noidung.md --target ./report.docx
  office-auto inspect --run-id run_2026-06-15T11-58-20-596Z

Exit codes:
  0  Success
  1  Pipeline failure (see JSON output for details)
  2  Invalid arguments
  3  Unexpected error
`);
}

async function handleGenerate(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      template: { type: 'string', short: 't' },
      source: { type: 'string', short: 's' },
      target: { type: 'string' },
    },
    strict: true,
  });

  if (!values.template || !values.source || !values.target) {
    console.error('Error: --template, --source, and --target are required');
    process.exit(2);
  }

  console.log('Starting pipeline...');
  console.log(`  Template: ${values.template}`);
  console.log(`  Source: ${values.source}`);
  console.log(`  Target: ${values.target}`);
  console.log('');

  try {
    const result = await runPipeline(values.template, values.source, values.target);

    if (result.ok) {
      console.log('✓ Pipeline completed successfully');
      console.log('');
      console.log(JSON.stringify({
        ok: true,
        run_id: result.run_id,
        run_dir: getRunDir(result.run_id),
        target_file: values.target,
        artifacts: result.artifacts,
      }, null, 2));
      process.exit(0);
    } else {
      console.error('✗ Pipeline failed');
      console.error('');
      console.error(JSON.stringify({
        ok: false,
        run_id: result.run_id,
        run_dir: getRunDir(result.run_id),
        error_code: result.error?.error_code,
        error_phase: result.error?.phase,
        error_message: result.error?.message,
        retryable: result.error?.retryable,
        artifacts: result.artifacts,
      }, null, 2));
      process.exit(1);
    }
  } catch (error) {
    console.error('✗ Unexpected error');
    console.error('');
    console.error(error);
    process.exit(3);
  }
}

async function handleInspect(args: string[]) {
  const { values } = parseArgs({
    args,
    options: {
      'run-id': { type: 'string', short: 'r' },
    },
    strict: true,
  });

  if (!values['run-id']) {
    console.error('Error: --run-id is required');
    process.exit(2);
  }

  try {
    const runDir = getRunDir(values['run-id']);
    const state = readRunState(values['run-id']);

    console.log('Run state:');
    console.log('');
    console.log(JSON.stringify({
      run_id: state.run_id,
      run_dir: runDir,
      status: state.status,
      current_phase: state.current_phase,
      template_file: state.template_file,
      source_file: state.source_file,
      target_file: state.target_file,
      error: state.error,
      created_at: state.created_at,
      updated_at: state.updated_at,
    }, null, 2));
    process.exit(0);
  } catch (error) {
    console.error('✗ Error reading run state');
    console.error('');
    console.error(error);
    process.exit(1);
  }
}

// Main entry point
const [command, ...rest] = process.argv.slice(2);

if (!command || command === '--help' || command === '-h') {
  printUsage();
  process.exit(0);
}

if (command === 'generate') {
  handleGenerate(rest);
} else if (command === 'inspect') {
  handleInspect(rest);
} else {
  console.error(`Unknown command: ${command}`);
  printUsage();
  process.exit(2);
}
