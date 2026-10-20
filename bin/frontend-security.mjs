#!/usr/bin/env node
import { spawnSync } from 'node:child_process';
import { resolve } from 'node:path';
import { realpathSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const toolRoot = resolve(fileURLToPath(new URL('../tools/frontend-security/', import.meta.url)));
const checker = fileURLToPath(new URL('../tools/frontend-security/scripts/check.ts', import.meta.url));
const help = `Usage: frontend-security --config PATH [--live]

Read-only, deterministic public-build security checks. Requires Bun 1.3+.
Configuration paths resolve from your cwd; artifact paths resolve from the config.
--live additionally probes configured owned origins; use only with permission.
Exit codes: 0 passed, 1 findings, 2 incomplete/error. No automatic fixes or deployment.
`;
export function run({argv = process.argv.slice(2), cwd = process.cwd(), execute = spawnSync, output = message => console.log(message)} = {}) {
  if (argv.length === 1 && ['--help','-h'].includes(argv[0])) { output(help); return 0; }
  let config, live = false;
  try {
    for (let i = 0; i < argv.length; i++) {
      if (argv[i] === '--config' && !config && argv[i+1] && !argv[i+1].startsWith('--')) config = resolve(cwd,argv[++i]);
      else if (argv[i] === '--live' && !live) live = true;
      else throw Error();
    }
    if (!config) throw Error();
    // A trusted cwd avoids executing the scanned project's Bun preloads/config.
    const result = execute('bun',[checker,'--config',config,...(live ? ['--live'] : [])],{cwd:toolRoot,stdio:'inherit'});
    if (result.error || ![0,1,2].includes(result.status)) throw Error();
    return result.status;
  } catch {
    output(JSON.stringify({schemaVersion:1,verdict:'incomplete',exitCode:2,error:'Unable to run checks. Supply --config PATH and install Bun 1.3+. Raw arguments and errors are not logged.'}));
    return 2;
  }
}
if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = run();
