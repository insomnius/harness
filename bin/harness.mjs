#!/usr/bin/env node

import {
  accessSync, constants, cpSync, existsSync, lstatSync, mkdirSync, mkdtempSync,
  readFileSync, readdirSync, realpathSync, renameSync, rmSync, statSync,
} from 'node:fs';
import { homedir } from 'node:os';
import { delimiter, dirname, join, resolve } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';

const packageRoot = fileURLToPath(new URL('../', import.meta.url));
const catalog = JSON.parse(readFileSync(join(packageRoot, '.claude-plugin/marketplace.json')));
const skillNames = catalog.plugins.map(plugin => plugin.name);
const agentNames = ['codex', 'claude-code'];
const marketplaceSource = 'insomnius/harness';

const help = `Usage: harness-skills [options]

Install both Harness skills for detected Codex and Claude Code installations.
Codex receives complete skill folders; Claude Code uses its plugin marketplace.
The default scope is the current project.

  --agent NAME   Target codex or claude-code; repeat to select both
  --skill NAME   Select ${skillNames.join(' or ')}; repeat for both
  -g, --global   Install for your user across projects
  --dry-run      Show targets and commands without changing anything
  --force        Replace different existing Codex skill folders
  -h, --help     Show this help
  --version      Show installer version

Detection checks for codex/claude on PATH and Codex's configuration directory.
Use --agent codex for a desktop-only installation not detected automatically.
Claude Code requires the claude CLI on PATH and access to the GitHub marketplace.
`;

function commandExists(name, environment) {
  const extensions = process.platform === 'win32'
    ? (environment.PATHEXT || '.EXE;.CMD;.BAT').split(';') : [''];
  const searchPath = environment.PATH ?? environment.Path ?? '';
  for (const directory of searchPath.split(delimiter).filter(Boolean)) {
    for (const extension of extensions) {
      const candidate = join(directory, name + extension.toLowerCase());
      try {
        accessSync(candidate, constants.X_OK);
        if (statSync(candidate).isFile()) return true;
      } catch {}
    }
  }
  return false;
}

function present(path) {
  try {
    return lstatSync(path);
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

function include(path) {
  return !path.split(/[\\/]/).some(part =>
    part === '__pycache__' || part === '.DS_Store' || /\.py[cod]$/.test(part));
}

function sameFiles(source, target) {
  try {
    const left = readdirSync(source).filter(include).sort();
    const right = readdirSync(target).filter(include).sort();
    if (JSON.stringify(left) !== JSON.stringify(right)) return false;
    return left.every(name => {
      const a = join(source, name);
      const b = join(target, name);
      const original = lstatSync(a);
      const installed = lstatSync(b);
      if (original.isDirectory() && installed.isDirectory()) return sameFiles(a, b);
      return original.isFile() && installed.isFile() && readFileSync(a).equals(readFileSync(b));
    });
  } catch (error) {
    if (['ENOENT', 'ENOTDIR'].includes(error.code)) return false;
    throw error;
  }
}

function copySkill(source, destination) {
  mkdirSync(dirname(destination), { recursive: true });
  const staging = mkdtempSync(join(dirname(destination), '.harness-'));
  const next = join(staging, 'next');
  const previous = join(staging, 'previous');
  try {
    cpSync(source, next, { recursive: true, filter: include });
    if (present(destination)) renameSync(destination, previous);
    try {
      renameSync(next, destination);
    } catch (error) {
      if (present(previous)) renameSync(previous, destination);
      throw error;
    }
  } finally {
    if (present(previous) && !present(destination)) {
      throw new Error(`Could not restore the previous skill; its files are preserved at ${previous}.`);
    }
    rmSync(staging, { recursive: true, force: true });
  }
}

export function install({
  argv = process.argv.slice(2),
  cwd = process.cwd(),
  userDirectory = homedir(),
  environment = process.env,
  output = message => console.log(message),
  errorOutput = message => console.error(message),
  execute = (command, args) => spawnSync(command, args, {
    cwd, env: environment, stdio: 'inherit', shell: process.platform === 'win32',
  }),
} = {}) {
  const { values } = parseArgs({ args: argv, options: {
    agent: { type: 'string', multiple: true },
    skill: { type: 'string', multiple: true },
    global: { type: 'boolean', short: 'g' },
    'dry-run': { type: 'boolean' },
    force: { type: 'boolean' },
    help: { type: 'boolean', short: 'h' },
    version: { type: 'boolean' },
  } });
  if (values.help) { output(help); return 0; }
  if (values.version) {
    output(JSON.parse(readFileSync(join(packageRoot, 'package.json'))).version);
    return 0;
  }
  const selectedSkills = [...new Set(values.skill ?? skillNames)];
  for (const skill of selectedSkills) {
    if (!skillNames.includes(skill)) throw new Error(`Unknown skill: ${skill}. Choose ${skillNames.join(', ')}.`);
  }
  for (const agent of values.agent ?? []) {
    if (!agentNames.includes(agent)) throw new Error(`Unknown agent: ${agent}. Choose ${agentNames.join(', ')}.`);
  }
  const available = {
    codex: commandExists('codex', environment) || existsSync(environment.CODEX_HOME || join(userDirectory, '.codex')),
    'claude-code': commandExists('claude', environment),
  };
  const selectedAgents = [...new Set(values.agent ?? agentNames.filter(name => available[name]))];
  if (!selectedAgents.length) {
    throw new Error('No supported agents detected. Install Codex or Claude Code, or use --agent codex for a desktop installation.');
  }
  if (selectedAgents.includes('claude-code') && !available['claude-code']) {
    throw new Error('Claude Code installation requires the claude CLI on PATH. Install it, or select --agent codex.');
  }

  const destinationRoot = join(values.global ? userDirectory : resolve(cwd), '.agents', 'skills');
  const copies = selectedAgents.includes('codex') ? selectedSkills.map(name => {
    const entry = catalog.plugins.find(plugin => plugin.name === name);
    const source = join(packageRoot, entry.source, 'skills', name);
    if (!existsSync(join(source, 'SKILL.md'))) throw new Error(`Missing bundled skill: ${name}.`);
    const destination = join(destinationRoot, name);
    const unchanged = present(destination) && sameFiles(source, destination);
    if (present(destination) && !unchanged && !values.force && !values['dry-run']) {
      throw new Error(`${destination} already exists with different content. Use --force to replace it, or keep the existing installation.`);
    }
    return { name, source, destination, unchanged };
  }) : [];

  output(`Agents: ${selectedAgents.join(', ')}${values.agent ? ' (selected)' : ' (detected)'}`);
  output(`Scope: ${values.global ? 'user' : `project (${resolve(cwd)})`}`);
  if (values['dry-run']) output('Dry run: no files or plugin settings will change.');
  let failed = false;
  for (const copy of copies) {
    if (copy.unchanged) { output(`Codex: ${copy.name} is already up to date.`); continue; }
    if (values['dry-run']) {
      const replacement = present(copy.destination)
        ? (values.force ? ' (replace existing)' : ' (exists; requires --force)') : '';
      output(`Codex: copy ${copy.name} to ${copy.destination}${replacement}`);
      continue;
    }
    try {
      copySkill(copy.source, copy.destination);
      output(`Codex: installed ${copy.name} at ${copy.destination}`);
    } catch (error) {
      errorOutput(`Codex: ${copy.name}: ${error.message}`);
      failed = true;
    }
  }

  if (selectedAgents.includes('claude-code')) {
    const scope = values.global ? 'user' : 'project';
    const commands = [
      ['plugin', 'marketplace', 'add', marketplaceSource, '--scope', scope],
      ...selectedSkills.map(name => ['plugin', 'install', `${name}@${catalog.name}`, '--scope', scope]),
    ];
    for (const args of commands) {
      output(`Claude Code: claude ${args.join(' ')}`);
      if (values['dry-run']) continue;
      const result = execute('claude', args);
      if (result.error || result.status !== 0) {
        errorOutput(`Claude Code failed: ${result.error?.message ?? `exit ${result.status ?? result.signal}`}. Rerun the command above after resolving the error.`);
        failed = true;
        break;
      }
    }
  }
  if (!values['dry-run'] && !failed) output('Installation complete. Start a new agent session to use the skills.');
  return failed ? 1 : 0;
}

if (process.argv[1] && realpathSync(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    process.exitCode = install();
  } catch (error) {
    console.error(`Harness: ${error.message}`);
    process.exitCode = 1;
  }
}
