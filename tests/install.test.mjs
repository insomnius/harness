import assert from 'node:assert/strict';
import {
  chmodSync, existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync,
  rmSync, statSync, symlinkSync, writeFileSync,
} from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { install } from '../bin/harness.mjs';

const repository = fileURLToPath(new URL('../', import.meta.url));

function fixture(t, agents = []) {
  const directory = mkdtempSync(join(tmpdir(), 'harness install-'));
  t.after(() => rmSync(directory, { recursive: true, force: true }));
  const cwd = join(directory, 'project');
  const userDirectory = join(directory, 'user');
  const binaries = join(directory, 'bin');
  for (const path of [cwd, userDirectory, binaries]) mkdirSync(path);
  for (const name of agents) {
    const binary = join(binaries, name + (process.platform === 'win32' ? '.cmd' : ''));
    writeFileSync(binary, '');
    chmodSync(binary, 0o755);
  }
  const commands = [];
  const messages = [];
  const errors = [];
  const options = {
    argv: [], cwd, userDirectory, environment: { PATH: binaries },
    output: message => messages.push(message),
    errorOutput: message => errors.push(message),
    execute: (command, args) => { commands.push([command, ...args]); return { status: 0 }; },
  };
  return { directory, cwd, userDirectory, binaries, commands, messages, errors, options };
}

test('no detected agents produces an actionable error without installing', t => {
  const f = fixture(t);
  assert.throws(() => install(f.options), /No supported agents detected/);
  assert.deepEqual(readdirSync(f.cwd), []);
  assert.deepEqual(f.commands, []);
});

for (const agent of ['codex', 'pi']) {
  test(`${agent} CLI detection installs both complete skills into the project`, t => {
    const f = fixture(t, [agent]);
    assert.equal(install(f.options), 0);
    for (const name of ['design-thinking', 'code-smells']) {
      const source = join(repository, 'plugins', name, 'skills', name);
      const target = join(f.cwd, '.agents/skills', name);
      const check = (a, b) => {
        for (const entry of readdirSync(a, { withFileTypes: true })) {
          if (entry.name === '__pycache__' || /\.py[cod]$/.test(entry.name)) continue;
          if (entry.isDirectory()) check(join(a, entry.name), join(b, entry.name));
          else assert.deepEqual(readFileSync(join(b, entry.name)), readFileSync(join(a, entry.name)));
        }
      };
      check(source, target);
    }
    assert.deepEqual(f.commands, []);
    assert.equal(existsSync(join(f.userDirectory, '.agents')), false);
  });
}

for (const agentDirectory of ['.pi/agent', 'custom-pi-agent']) {
  test(`Pi configuration detection supports ${agentDirectory} without the CLI`, t => {
    const f = fixture(t);
    const directory = join(f.userDirectory, agentDirectory);
    mkdirSync(directory, { recursive: true });
    const environment = { ...f.options.environment };
    if (agentDirectory === 'custom-pi-agent') environment.PI_CODING_AGENT_DIR = directory;
    assert.equal(install({ ...f.options, environment }), 0);
    assert.ok(existsSync(join(f.cwd, '.agents/skills/design-thinking/SKILL.md')));
    assert.ok(f.messages.some(message => message === 'Agents: pi (detected)'));
  });
}

test('explicit Pi selection works before installation and selects only the requested skill', t => {
  const f = fixture(t, ['codex', 'claude']);
  assert.equal(install({ ...f.options, argv: ['--agent', 'pi', '--skill', 'code-smells'] }), 0);
  assert.deepEqual(readdirSync(join(f.cwd, '.agents/skills')), ['code-smells']);
  assert.deepEqual(f.commands, []);
});

test('Codex configuration detects a desktop setup without the CLI', t => {
  const f = fixture(t);
  mkdirSync(join(f.userDirectory, '.codex'));
  assert.equal(install(f.options), 0);
  assert.ok(existsSync(join(f.cwd, '.agents/skills/design-thinking/SKILL.md')));
});

test('explicit selection permits Codex setup before a client is installed', t => {
  const f = fixture(t);
  assert.equal(install({ ...f.options, argv: ['--agent', 'codex', '--skill', 'code-smells'] }), 0);
  assert.deepEqual(readdirSync(join(f.cwd, '.agents/skills')), ['code-smells']);
});

test('all clients are detected and Codex/Pi share one copy alongside Claude plugins', t => {
  const f = fixture(t, ['claude', 'codex', 'pi']);
  assert.equal(install(f.options), 0);
  assert.ok(existsSync(join(f.cwd, '.agents/skills/design-thinking/scripts/design.py')));
  assert.ok(f.messages.some(message => message === 'Agents: codex, claude-code, pi (detected)'));
  assert.equal(f.messages.filter(message => message.startsWith('Codex/Pi: installed')).length, 2);
  assert.deepEqual(f.commands, [
    ['claude', 'plugin', 'marketplace', 'add', 'insomnius/harness', '--scope', 'project'],
    ['claude', 'plugin', 'install', 'design-thinking@harness', '--scope', 'project'],
    ['claude', 'plugin', 'install', 'code-smells@harness', '--scope', 'project'],
  ]);
});

test('Claude-only detection does not create Codex skill folders', t => {
  const f = fixture(t, ['claude']);
  assert.equal(install(f.options), 0);
  assert.equal(existsSync(join(f.cwd, '.agents')), false);
  assert.equal(f.commands.length, 3);
});

test('global installation targets shared Codex/Pi user skills and Claude user scope', t => {
  const f = fixture(t, ['claude', 'codex', 'pi']);
  assert.equal(install({ ...f.options, argv: ['--global'] }), 0);
  assert.ok(existsSync(join(f.userDirectory, '.agents/skills/code-smells/SKILL.md')));
  assert.equal(existsSync(join(f.cwd, '.agents')), false);
  assert.ok(f.commands.every(command => command.at(-1) === 'user'));
});

test('explicit agent and skill choices narrow the installation', t => {
  const f = fixture(t, ['claude', 'codex']);
  assert.equal(install({ ...f.options, argv: ['--agent', 'claude-code', '--skill', 'code-smells'] }), 0);
  assert.equal(existsSync(join(f.cwd, '.agents')), false);
  assert.equal(f.commands.length, 2);
  assert.equal(f.commands[1][3], 'code-smells@harness');
});

test('dry run detects clients and reports actions without writes or commands', t => {
  const f = fixture(t, ['claude', 'codex', 'pi']);
  assert.equal(install({ ...f.options, argv: ['--dry-run'] }), 0);
  assert.deepEqual(readdirSync(f.cwd), []);
  assert.deepEqual(readdirSync(f.userDirectory), []);
  assert.deepEqual(f.commands, []);
  assert.ok(f.messages.some(message => message.includes('design-thinking@harness')));
});

for (const agent of ['codex', 'pi']) {
  test(`an unchanged ${agent} installation is a no-op`, t => {
    const f = fixture(t, [agent]);
    install(f.options);
    const target = join(f.cwd, '.agents/skills/design-thinking/SKILL.md');
    const before = statSync(target);
    assert.equal(install(f.options), 0);
    assert.equal(statSync(target).mtimeMs, before.mtimeMs);
    assert.ok(f.messages.some(message => message.includes('already up to date')));
  });

  test(`${agent} differing skills are preserved and checked before any installation`, t => {
    const f = fixture(t, [agent, 'claude']);
    const target = join(f.cwd, '.agents/skills/code-smells');
    mkdirSync(target, { recursive: true });
    writeFileSync(join(target, 'SKILL.md'), 'my custom skill');
    assert.throws(() => install(f.options), /--force/);
    assert.equal(readFileSync(join(target, 'SKILL.md'), 'utf8'), 'my custom skill');
    assert.equal(existsSync(join(f.cwd, '.agents/skills/design-thinking')), false);
    assert.deepEqual(f.commands, []);
  });

  test(`${agent} force replaces the selected skill and removes obsolete files`, t => {
    const f = fixture(t, [agent]);
    const target = join(f.cwd, '.agents/skills/code-smells');
    mkdirSync(target, { recursive: true });
    writeFileSync(join(target, 'old.txt'), 'old content');
    assert.equal(install({ ...f.options, argv: ['--skill', 'code-smells', '--force'] }), 0);
    assert.ok(existsSync(join(target, 'SKILL.md')));
    assert.equal(existsSync(join(target, 'old.txt')), false);
    assert.deepEqual(readdirSync(join(f.cwd, '.agents/skills')), ['code-smells']);
  });

  test(`${agent} dry run reports a conflict without changing it`, t => {
    const f = fixture(t, [agent]);
    const target = join(f.cwd, '.agents/skills/code-smells');
    mkdirSync(target, { recursive: true });
    writeFileSync(join(target, 'SKILL.md'), 'custom');
    assert.equal(install({ ...f.options, argv: ['--dry-run'] }), 0);
    assert.equal(readFileSync(join(target, 'SKILL.md'), 'utf8'), 'custom');
    assert.equal(existsSync(join(f.cwd, '.agents/skills/design-thinking')), false);
    assert.ok(f.messages.some(message => message.includes('exists; requires --force')));
  });
}

test('Pi global-only selection installs into the shared user location', t => {
  const f = fixture(t);
  assert.equal(install({ ...f.options, argv: ['--agent', 'pi', '--global'] }), 0);
  assert.ok(existsSync(join(f.userDirectory, '.agents/skills/design-thinking/scripts/design.py')));
  assert.ok(existsSync(join(f.userDirectory, '.agents/skills/code-smells/SKILL.md')));
  assert.deepEqual(readdirSync(f.cwd), []);
  assert.deepEqual(f.commands, []);
});

test('repeated explicit Codex/Pi selections install each shared skill once', t => {
  const f = fixture(t);
  assert.equal(install({ ...f.options, argv: ['--agent', 'pi', '--agent', 'codex', '--agent', 'pi'] }), 0);
  assert.equal(f.messages.filter(message => message.startsWith('Pi/Codex: installed')).length, 2);
  assert.deepEqual(readdirSync(join(f.cwd, '.agents/skills')).sort(), ['code-smells', 'design-thinking']);
});

test('force replaces a symlink without modifying its original target', t => {
  const f = fixture(t, ['codex']);
  const original = join(f.directory, 'custom-skill');
  mkdirSync(original);
  writeFileSync(join(original, 'SKILL.md'), 'preserve this');
  const target = join(f.cwd, '.agents/skills/code-smells');
  mkdirSync(join(f.cwd, '.agents/skills'), { recursive: true });
  symlinkSync(original, target, 'junction');
  assert.equal(install({ ...f.options, argv: ['--skill', 'code-smells', '--force'] }), 0);
  assert.equal(readFileSync(join(original, 'SKILL.md'), 'utf8'), 'preserve this');
  assert.notEqual(readFileSync(join(target, 'SKILL.md'), 'utf8'), 'preserve this');
});

test('invalid selections and a missing Claude CLI fail before side effects', t => {
  const f = fixture(t);
  for (const argv of [['--agent', 'other'], ['--skill', '../other'], ['--agent', 'claude-code'], ['--unknown']]) {
    assert.throws(() => install({ ...f.options, argv }));
    assert.deepEqual(readdirSync(f.cwd), []);
    assert.deepEqual(f.commands, []);
  }
});

test('Claude command failure is reported and does not claim a successful install', t => {
  const f = fixture(t, ['claude', 'codex']);
  const execute = (command, args) => {
    f.commands.push([command, ...args]);
    return { status: 7 };
  };
  assert.equal(install({ ...f.options, execute }), 1);
  assert.equal(f.commands.length, 1);
  assert.ok(f.errors.some(message => message.includes('exit 7')));
  assert.ok(existsSync(join(f.cwd, '.agents/skills/design-thinking/SKILL.md')));
  assert.equal(f.messages.some(message => message.startsWith('Installation complete')), false);
});

test('the executable returns nonzero for invalid input', t => {
  const f = fixture(t);
  const result = spawnSync(process.execPath, [join(repository, 'bin/harness.mjs'), '--agent', 'unknown'], {
    cwd: f.cwd, encoding: 'utf8',
  });
  assert.ifError(result.error);
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unknown agent/);
  assert.deepEqual(readdirSync(f.cwd), []);
});

test('the executable runs the Claude CLI with separate arguments', { skip: process.platform === 'win32' }, t => {
  const f = fixture(t, ['claude']);
  const log = join(f.directory, 'commands.jsonl');
  writeFileSync(join(f.binaries, 'claude'), `#!${process.execPath}\nimport { appendFileSync } from 'node:fs';\nappendFileSync(process.env.HARNESS_INSTALL_TEST_LOG, JSON.stringify(process.argv.slice(2)) + '\\n');\n`);
  const result = spawnSync(process.execPath, [join(repository, 'bin/harness.mjs'), '--agent', 'claude-code', '--skill', 'code-smells'], {
    cwd: f.cwd, encoding: 'utf8', env: { ...process.env, PATH: f.binaries, HARNESS_INSTALL_TEST_LOG: log },
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(readFileSync(log, 'utf8').trim().split('\n').map(line => JSON.parse(line)), [
    ['plugin', 'marketplace', 'add', 'insomnius/harness', '--scope', 'project'],
    ['plugin', 'install', 'code-smells@harness', '--scope', 'project'],
  ]);
});

test('the npm package includes every skill resource and excludes generated files', t => {
  const f = fixture(t);
  const result = spawnSync('npm', ['pack', '--dry-run', '--json', '--ignore-scripts', '--cache', join(f.directory, 'cache')], {
    cwd: repository, encoding: 'utf8', shell: process.platform === 'win32',
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stderr);
  const [packed] = JSON.parse(result.stdout);
  const paths = new Set(packed.files.map(file => file.path));
  assert.ok(paths.has('bin/harness.mjs'));
  assert.ok(paths.has('.claude-plugin/marketplace.json'));
  assert.ok(paths.has('plugins/design-thinking/UPSTREAM.md'));
  assert.equal([...paths].some(path => path.includes('__pycache__') || path.endsWith('.pyc') || path.startsWith('benchmark/')), false);
  const check = directory => {
    for (const entry of readdirSync(join(repository, directory), { withFileTypes: true })) {
      if (entry.name === '__pycache__' || /\.py[cod]$/.test(entry.name)) continue;
      const path = `${directory}/${entry.name}`;
      if (entry.isDirectory()) check(path);
      else assert.ok(paths.has(path), `Missing packaged resource: ${path}`);
    }
  };
  check('plugins/design-thinking/skills/design-thinking');
  check('plugins/code-smells/skills/code-smells');
});
