import { lstat, readdir, open } from 'node:fs/promises';
import { constants } from 'node:fs';
import { resolve, join } from 'node:path';
import { gunzipSync, brotliDecompressSync } from 'node:zlib';
import { comparisons, inspect, privatePath, redact, exitCode, type Finding } from './policy';

type Options = {mode: string; roots: string[]; urls: string[]; extra: string[]; allowed: string[]; maxBytes: number; timeout: number};
export function argumentsFor(args: string[]): Options {
  const result: Options = {mode: args.shift() || 'help', roots: [], urls: [], extra: [], allowed: [], maxBytes: 64 * 1024 * 1024, timeout: 8000};
  for (let i = 0; i < args.length; i++) {
    const flag = args[i], value = args[++i];
    if (!value) throw Error('Invalid arguments');
    if (flag === '--root') result.roots.push(value);
    else if (flag === '--url') result.urls.push(value);
    else if (flag === '--compare-env' || flag === '--allow-env') {
      if (!/^[A-Z_][A-Z0-9_]*$/.test(value)) throw Error('Use environment names, never values');
      (flag === '--compare-env' ? result.extra : result.allowed).push(value);
    } else if (flag === '--max-file-mib') {
      if (!/^\d+$/.test(value) || +value < 1 || +value > 256) throw Error('Invalid size limit');
      result.maxBytes = +value * 1024 * 1024;
    } else if (flag === '--timeout-ms') {
      if (!/^\d+$/.test(value) || +value < 100 || +value > 30000) throw Error('Invalid timeout');
      result.timeout = +value;
    } else throw Error('Unknown option');
  }
  if (result.roots.length > 20 || result.urls.length > 10) throw Error('Target budget exceeded');
  return result;
}

async function readBounded(path: string, maximum: number): Promise<Buffer | null> {
  const file = await open(path, constants.O_RDONLY | (constants.O_NOFOLLOW ?? 0));
  try {
    const info = await file.stat();
    if (!info.isFile() || info.size > maximum) return null;
    const chunks: Buffer[] = []; let size = 0;
    while (size <= maximum) {
      const buffer = Buffer.allocUnsafe(Math.min(131072, maximum + 1 - size));
      const {bytesRead} = await file.read(buffer);
      if (!bytesRead) return Buffer.concat(chunks);
      size += bytesRead; chunks.push(buffer.subarray(0, bytesRead));
    }
    return null;
  } finally { await file.close(); }
}

export async function scan(roots: string[], values: [string,string][], maxBytes: number) {
  const findings: Finding[] = [], warnings: Finding[] = [];
  let files = 0, bytes = 0, visited = 0, exhausted = false;
  async function walk(path: string, relative: string) {
    if (exhausted) return;
    if (++visited > 100000 || bytes > 512 * 1024 * 1024) { exhausted = true; warnings.push({kind: 'scan-budget-exceeded', path: relative}); return; }
    try {
      const info = await lstat(path);
      if (info.isSymbolicLink()) { warnings.push({kind: 'symlink-not-followed', path: relative}); return; }
      if (info.isDirectory()) {
        if (relative && privatePath(relative)) findings.push({kind: 'private-artifact-directory', path: relative});
        for (const name of (await readdir(path)).sort()) await walk(join(path, name), relative ? `${relative}/${name}` : name);
        return;
      }
      if (!info.isFile()) { warnings.push({kind: 'nonregular-file-not-scanned', path: relative}); return; }
      if (info.size > maxBytes) { warnings.push({kind: 'oversized-file-not-scanned', path: relative}); return; }
      const data = await readBounded(path, maxBytes);
      if (!data) { warnings.push({kind: 'oversized-or-changed-file-not-scanned', path: relative}); return; }
      files++; bytes += data.length;
      findings.push(...inspect(data, relative, values));
      if (/\.(?:zip|tar|tgz|7z|rar|xz|zst)$/i.test(relative)) warnings.push({kind: 'archive-not-inspected', path: relative});
      if (/\.(?:gz|br)$/i.test(relative)) {
        if (!/\.(?:js|css|json|html|txt|map)\.(?:gz|br)$/i.test(relative)) warnings.push({kind: 'archive-not-inspected', path: relative});
        else {
          const allowance = Math.min(maxBytes, 512 * 1024 * 1024 - bytes);
          try {
            if (allowance <= 0) throw Error();
            const decoded = relative.endsWith('.gz') ? gunzipSync(data, {maxOutputLength: allowance}) : brotliDecompressSync(data, {maxOutputLength: allowance});
            bytes += decoded.length;
            findings.push(...inspect(decoded, relative.replace(/\.(?:gz|br)$/i, ''), values));
          } catch {
            bytes += Math.max(0, allowance); // Charge failed decompression attempts to the work budget too.
            warnings.push({kind: 'compressed-file-not-inspected', path: relative});
          }
        }
      }
    } catch { warnings.push({kind: 'unreadable-path', path: relative}); }
  }
  for (const root of roots) {
    try {
      if (!(await lstat(resolve(root))).isDirectory()) { warnings.push({kind: 'invalid-or-linked-root', path: root}); continue; }
      await walk(resolve(root), '');
    } catch { warnings.push({kind: 'missing-root', path: root}); }
  }
  return {mode: 'artifact-only', roots: roots.map(root => resolve(root)), files, bytes, findings, warnings};
}

const probePaths = ['.env', '.env.production', '.env.local', 'assets/.env', '.git/config', 'config.env', 'server.pem', 'server.key', 'assets/private.js.map'];
export async function probe(urls: string[], values: [string,string][], timeout: number) {
  const findings: Finding[] = [], warnings: Finding[] = [], checks: {url:string;status:number}[] = [];
  for (const input of urls) {
    let base: URL;
    try {
      base = new URL(input);
      if (!['https:', 'http:'].includes(base.protocol) || base.username || base.password || base.search || base.hash) throw Error();
      if (base.protocol === 'http:' && !['localhost','127.0.0.1','[::1]'].includes(base.hostname)) throw Error();
      if (!base.pathname.endsWith('/')) base.pathname += '/';
    } catch { warnings.push({kind: 'invalid-unsafe-or-insecure-origin'}); continue; }
    for (const path of probePaths) {
      const target = new URL(path, base);
      try {
        const response = await fetch(target, {redirect: 'manual', credentials: 'omit', signal: AbortSignal.timeout(timeout), headers: {'User-Agent':'frontend-env-security/read-only-audit'}});
        checks.push({url: target.href, status: response.status});
        if ([403,404,410].includes(response.status)) { await response.body?.cancel(); continue; }
        if (response.status !== 200) { await response.body?.cancel(); warnings.push({kind: 'redirect-auth-or-unexpected-status-not-followed', path: target.href}); continue; }
        const reader = response.body?.getReader(), chunks: Uint8Array[] = [];
        let size = 0, truncated = false;
        if (reader) {
          while (true) {
            const next = await reader.read(); if (next.done) break;
            if (size + next.value.length > 65536) { truncated = true; await reader.cancel(); break; }
            size += next.value.length; chunks.push(next.value);
          }
        }
        const data = Buffer.concat(chunks);
        const matches = inspect(data, target.href, values).filter(f => f.kind !== 'private-artifact');
        findings.push(...matches);
        const html = response.headers.get('content-type')?.includes('text/html') || /^\s*(?:<!doctype html|<html)/i.test(data.toString());
        if (!html && /^(?:export\s+)?[A-Z_][A-Z0-9_]*\s*=\s*\S+/m.test(data.toString())) findings.push({kind: 'environment-format-response', path: target.href});
        else if (!matches.length) warnings.push({kind: html ? 'http-200-html-may-be-spa-fallback' : 'http-200-needs-private-content-review', path: target.href});
        if (truncated) warnings.push({kind: 'http-response-truncated', path: target.href});
      } catch { warnings.push({kind: 'network-or-tls-failure', path: target.href}); }
    }
  }
  return {mode: 'unauthenticated-http-only', checks, findings, warnings};
}

async function main() {
  let options: Options;
  try { options = argumentsFor(process.argv.slice(2)); } catch { console.log(JSON.stringify({error:'Invalid arguments. Use names/owned origins, not credentials.'})); process.exitCode = 2; return; }
  if (options.mode === 'help') { console.log('scan --root ABSOLUTE_PATH | probe --url OWNED_HTTPS_ORIGIN [--compare-env NAME] [--allow-env NAME] [--max-file-mib 64]'); return; }
  const selected = comparisons(process.env, options.extra, options.allowed);
  try {
    let report;
    if (options.mode === 'scan' && options.roots.length && !options.urls.length) report = await scan(options.roots, selected.values, options.maxBytes);
    else if (options.mode === 'probe' && options.urls.length && !options.roots.length) report = await probe(options.urls, selected.values, options.timeout);
    else throw Error();
    report.warnings.push(...selected.warnings);
    console.log(JSON.stringify(redact({...report, reviewedPublicExceptions: options.allowed, comparisonSource: 'current-process-environment', comparedValues: selected.values.filter(([,v]) => Buffer.byteLength(v) >= 8).length}, selected.values), null, 2));
    process.exitCode = exitCode(report.findings, report.warnings);
  } catch { console.log(JSON.stringify({error:'Audit failed; no raw exception or secret output was emitted.'})); process.exitCode = 2; }
}
if (import.meta.main) await main();
