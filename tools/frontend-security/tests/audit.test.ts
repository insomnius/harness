import { test, expect, afterEach } from 'bun:test';
import { mkdtemp, writeFile, symlink, rm, mkdir, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';
import { scan, probe, argumentsFor } from '../scripts/audit';
import { privatePath, inspect, comparisons, variants, redact, exitCode, patterns } from '../scripts/policy';

const directories: string[] = [];
async function temp() { const root = await mkdtemp(join(tmpdir(), 'env-skill-')); directories.push(root); return root; }
afterEach(async () => { await Promise.all(directories.splice(0).map(root => rm(root, {recursive:true, force:true}))); });
const skill = new URL('../', import.meta.url).pathname;
const script = new URL('../scripts/audit.ts', import.meta.url).pathname;
const runtime = new URL('../scripts/runtime_audit.py', import.meta.url).pathname;
const runtimeTest = Bun.which('python3') ? test : test.skip;

test('private paths fail while public data/media and well-known remain allowed', () => {
  for (const path of ['.env', 'config.env.production', 'assets/.env', '.git/config', 'server.key', 'data.db-wal', 'app.js.map', 'src/main.ts', '.well-known/.env']) expect(privatePath(path)).toBe(true);
  for (const path of ['crossword-bank.json', 'tutorial.mp4', 'font.woff2', 'resources/screenshot.webp', '.well-known/security.txt', '.well-known/acme-challenge/challenge']) expect(privatePath(path)).toBe(false);
});

test('known values are detected and redacted in raw and common encoded forms', () => {
  const value = 'synthetic-"private"/value\n123456789';
  const selected: [string,string][] = [['TEST_PRIVATE_TOKEN', value]];
  for (const form of variants(value)) {
    expect(inspect(Buffer.from(form), 'app.js', selected).some(f => f.kind === 'known-environment-value')).toBe(true);
    expect(JSON.stringify(redact({path: form}, selected))).not.toContain(form);
  }
  const token = 'ghp_' + 'x'.repeat(36);
  expect(inspect(Buffer.from(token), 'app.js', []).some(f => f.kind === 'github-token')).toBe(true);
  expect(JSON.stringify(redact({path:token}, []))).not.toContain(token);
});

test('missing/short comparisons are explicit and public exceptions are opt-in', () => {
  const selected = comparisons({API_KEY:'synthetic-private-value', PUBLIC_ID:'public-id', PASSWORD:'tiny'}, ['MISSING','PUBLIC_ID'], ['API_KEY']);
  expect(selected.values.map(([name]) => name)).toEqual(['PASSWORD','PUBLIC_ID']);
  expect(selected.warnings.map(w => w.kind)).toContain('comparison-value-unavailable');
  expect(selected.warnings.map(w => w.kind)).toContain('short-value-not-reliably-scannable');
  expect(exitCode([], selected.warnings)).toBe(2);
});

test('scan includes nested files, source maps and private filenames', async () => {
  const root = await temp(); await mkdir(join(root, 'assets'));
  await writeFile(join(root, '.env.production'), 'PUBLIC_ID=example');
  await writeFile(join(root, 'assets/main.js'), 'export {};\n//# sourceMappingURL=main.js.map');
  const report = await scan([root], [], 1024);
  expect(report.files).toBe(2);
  expect(report.findings.map(f => f.kind)).toContain('private-artifact');
  expect(report.findings.map(f => f.kind)).toContain('source-map-reference');
  expect(exitCode(report.findings, report.warnings)).toBe(1);
});

test('links, missing roots, archives and oversized files are never silently clean', async () => {
  const root = await temp(), outside = await temp();
  await writeFile(join(outside, 'outside.txt'), 'must-not-be-read');
  await symlink(join(outside, 'outside.txt'), join(root, 'alias'));
  await writeFile(join(root, 'large.txt'), 'larger-than-limit');
  await writeFile(join(root, 'out.zip'), 'zip');
  const report = await scan([root, join(root,'missing')], [['TEST_PRIVATE_TOKEN','must-not-be-read']], 8);
  expect(report.findings).toHaveLength(0);
  for (const kind of ['symlink-not-followed','oversized-file-not-scanned','archive-not-inspected','missing-root']) expect(report.warnings.map(w => w.kind)).toContain(kind);
  expect(exitCode(report.findings, report.warnings)).toBe(2);
});

test('precompressed JavaScript is inspected, not merely byte-matched as gzip', async () => {
  const root = await temp(), value = 'synthetic-private-value-123456789';
  await writeFile(join(root, 'main.js.gz'), gzipSync(Buffer.from(`const key=${JSON.stringify(value)}`)));
  const report = await scan([root], [['TEST_PRIVATE_TOKEN',value]], 1024 * 1024);
  expect(report.findings.some(f => f.kind === 'known-environment-value')).toBe(true);
});

test('HTTP probes accept observed denial with bounded same-origin requests', async () => {
  let requests = 0;
  const server = Bun.serve({hostname:'127.0.0.1', port:0, fetch() { requests++; return new Response('not found', {status:404}); }});
  try {
    const report = await probe([server.url.origin], [], 2000);
    expect(requests).toBe(9); expect(report.checks).toHaveLength(9);
    expect(exitCode(report.findings, report.warnings)).toBe(0);
  } finally { server.stop(true); }
});

test('SPA 200 is not a confirmed env leak; redirects are not followed; no bodies reported', async () => {
  const body = 'SYNTHETIC_PRIVATE_TOKEN=not-a-real-credential-123456';
  const server = Bun.serve({hostname:'127.0.0.1', port:0, fetch(request) {
    const path = new URL(request.url).pathname;
    if (path === '/.env') return new Response('<!doctype html><title>SPA</title>', {headers:{'Content-Type':'text/html'}});
    if (path === '/.env.production') return new Response(body, {headers:{'Content-Type':'text/plain'}});
    if (path === '/.git/config') return new Response(null, {status:302,headers:{Location:'https://third-party.invalid/never-follow'}});
    return new Response('not found', {status:404});
  }});
  try {
    const report = await probe([server.url.origin], [], 2000);
    expect(report.findings).toEqual([{kind:'environment-format-response',path:server.url.origin+'/.env.production'}]);
    expect(report.warnings.map(w => w.kind)).toContain('http-200-html-may-be-spa-fallback');
    expect(report.warnings.map(w => w.kind)).toContain('redirect-auth-or-unexpected-status-not-followed');
    expect(JSON.stringify(report)).not.toContain(body);
    expect(JSON.stringify(report)).not.toContain('third-party.invalid');
  } finally { server.stop(true); }
});

test('credential-bearing/insecure URLs and unlimited target arguments are rejected', async () => {
  const report = await probe(['https://user:synthetic-password@owned.invalid', 'https://owned.invalid/?token=synthetic-value','http://owned.invalid'], [], 100);
  expect(report.checks).toHaveLength(0); expect(report.warnings).toHaveLength(3);
  expect(JSON.stringify(report)).not.toContain('synthetic-password');
  expect(() => argumentsFor(['scan','--secret','do-not-echo'])).toThrow();
  expect(() => argumentsFor(['probe',...Array(11).fill(['--url','https://owned.invalid']).flat()])).toThrow();
});

test('actual CLI failure logs never expose known values, including in filenames', async () => {
  const root = await temp(), value = 'synthetic-private-canary-123456789';
  await writeFile(join(root, value+'.json'), JSON.stringify({value}));
  const child = Bun.spawn([process.execPath, script, 'scan','--root',root], {cwd:skill, env:{PATH:process.env.PATH!,HOME:process.env.HOME!,TEST_PRIVATE_TOKEN:value},stdout:'pipe',stderr:'pipe'});
  const [code, stdout, stderr] = await Promise.all([child.exited,new Response(child.stdout).text(),new Response(child.stderr).text()]);
  expect(code).toBe(1); expect(stdout).not.toContain(value); expect(stderr).toBe('');
  expect(JSON.parse(stdout).findings.some((f: any) => f.kind === 'known-environment-value')).toBe(true);
});

runtimeTest('standalone runtime audit uses mocked Docker, never extracts, and redacts reports', async () => {
  const code = `import sys, importlib.util, json, io, tarfile, types
sys.dont_write_bytecode=True
spec=importlib.util.spec_from_file_location('runtime_audit',sys.argv[1]); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
value='synthetic-private-runtime-canary-123456789'
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w') as tar:
 data=('const privateValue='+json.dumps(value)).encode(); entry=tarfile.TarInfo(value+'.js'); entry.size=len(data); tar.addfile(entry,io.BytesIO(data))
 link=tarfile.TarInfo('alias'); link.type=tarfile.SYMTYPE; link.linkname='/outside/secret'; tar.addfile(link)
def capture(cmd,maximum,timeout=60):
 if cmd==['docker','context','show']: return b'default'
 if cmd[:3]==['docker','context','inspect']: return json.dumps([{'Endpoints':{'docker':{'Host':'unix:///var/run/docker.sock'}}}]).encode()
 if 'inspect' in cmd: return json.dumps([{'Config':{'Env':['JWT_SECRET='+value] if cmd[-1]=='backend' else []}}]).encode()
 if 'cp' in cmd: return buffer.getvalue()
 raise RuntimeError()
m.capture=capture
report,secrets=m.audit(types.SimpleNamespace(context=None,container=['frontend'],compare_env_from=['backend'],web_root='/usr/share/nginx/html',max_archive_mib=1))
print(json.dumps({'report':m.redact(report,secrets),'patterns':m.PATTERNS}))`;
  const child = Bun.spawn(['python3','-B','-c',code,runtime], {cwd:skill,stdout:'pipe',stderr:'pipe'});
  const [status, stdout, stderr] = await Promise.all([child.exited,new Response(child.stdout).text(),new Response(child.stderr).text()]);
  expect(status).toBe(0); expect(stderr).toBe('');
  expect(stdout).not.toContain('synthetic-private-runtime-canary-123456789');
  const {report, patterns: runtimePatterns} = JSON.parse(stdout);
  expect(runtimePatterns).toEqual(patterns);
  expect(report.services[0].files).toBe(1);
  expect(report.findings[0].kind).toBe('known-environment-value');
  expect(report.warnings[0].kind).toBe('link-or-nonregular-member-not-followed');
});

runtimeTest('runtime argument errors do not echo supplied values', async () => {
  const value = 'synthetic-do-not-log-canary';
  const child = Bun.spawn(['python3','-B',runtime,'--container','frontend','--max-archive-mib',value], {stdout:'pipe',stderr:'pipe'});
  const [status, stdout, stderr] = await Promise.all([child.exited,new Response(child.stdout).text(),new Response(child.stderr).text()]);
  expect(status).toBe(2); expect(stdout+stderr).not.toContain(value); expect(stderr).toBe('');
});

test('standalone tool has a checked configuration and no Pi dependency', async () => {
  const config = JSON.parse(await readFile(join(skill, 'frontend-security.config.example.json'),'utf8'));
  const pkg = JSON.parse(await readFile(join(skill, 'package.json'),'utf8'));
  expect(config.version).toBe(1); expect(config.targets).toHaveLength(1);
  expect(pkg.pi).toBeUndefined(); expect(pkg.dependencies).toBeUndefined();
  expect(await Bun.file(join(skill,'references/checklist.md')).exists()).toBe(true);
});
