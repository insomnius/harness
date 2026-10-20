import { readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { scan, probe } from './audit';
import { comparisons, exitCode, redact } from './policy';

export type Config = {
  version: 1;
  maxFileMiB: number;
  timeoutMs: number;
  compareEnv: string[];
  publicEnv: string[];
  targets: {name: string; root: string; origin?: string}[];
};
function exactKeys(value: unknown, keys: string[]): value is Record<string, unknown> {
  return !!value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).every(key => keys.includes(key));
}
function envNames(value: unknown): value is string[] {
  return Array.isArray(value) && value.length <= 100 && value.every(name => typeof name === 'string' && /^[A-Z_][A-Z0-9_]*$/.test(name)) && new Set(value).size === value.length;
}
export function validateConfig(value: unknown): Config {
  if (!exactKeys(value, ['version','maxFileMiB','timeoutMs','compareEnv','publicEnv','targets']) || value.version !== 1 ||
      !Number.isInteger(value.maxFileMiB) || (value.maxFileMiB as number) < 1 || (value.maxFileMiB as number) > 256 ||
      !Number.isInteger(value.timeoutMs) || (value.timeoutMs as number) < 100 || (value.timeoutMs as number) > 30000 ||
      !envNames(value.compareEnv) || !envNames(value.publicEnv) ||
      !Array.isArray(value.targets) || !value.targets.length || value.targets.length > 20) throw Error('Invalid security configuration');
  const names = new Set<string>();
  for (const target of value.targets) {
    if (!exactKeys(target,['name','root','origin']) || typeof target.name !== 'string' || !/^[a-z0-9][a-z0-9-]{0,63}$/.test(target.name) || names.has(target.name) ||
        typeof target.root !== 'string' || !target.root || /[\x00-\x1f]/.test(target.root)) throw Error('Invalid target configuration');
    names.add(target.name);
    if (target.origin !== undefined) {
      if (typeof target.origin !== 'string') throw Error('Invalid origin');
      const url = new URL(target.origin);
      if (url.username || url.password || url.search || url.hash || !['https:','http:'].includes(url.protocol) ||
          (url.protocol === 'http:' && !['localhost','127.0.0.1','[::1]'].includes(url.hostname))) throw Error('Invalid origin');
    }
  }
  return value as Config;
}
function sorted<T>(items: T[]): T[] {
  return [...items].sort((a,b) => { const x=JSON.stringify(a), y=JSON.stringify(b); return x < y ? -1 : x > y ? 1 : 0; });
}
export async function check(config: Config, configDirectory: string, live: boolean, env: Record<string,string|undefined> = process.env) {
  const selected = comparisons(env, config.compareEnv, config.publicEnv);
  const targets = [];
  for (const target of [...config.targets].sort((a,b) => a.name < b.name ? -1 : a.name > b.name ? 1 : 0)) {
    const artifact = await scan([resolve(configDirectory,target.root)], selected.values, config.maxFileMiB * 1024 * 1024);
    const http = live && target.origin ? await probe([target.origin], selected.values,config.timeoutMs) : null;
    if (live && !target.origin) artifact.warnings.push({kind:'live-origin-not-configured',path:target.name});
    targets.push({name:target.name, artifact: {...artifact,findings:sorted(artifact.findings),warnings:sorted(artifact.warnings)},
      http: http ? {...http,findings:sorted(http.findings),warnings:sorted(http.warnings)} : null});
  }
  const findings = targets.flatMap(target => [...target.artifact.findings,...(target.http?.findings || [])]);
  const warnings = [...selected.warnings,...targets.flatMap(target => [...target.artifact.warnings,...(target.http?.warnings || [])])];
  const code = exitCode(findings,warnings);
  const report = {schemaVersion:1,exitCode:code,verdict:code === 0 ? 'passed' : code === 1 ? 'findings' : 'incomplete',
    coverageComplete:warnings.length === 0,mode:live ? 'artifacts-and-configured-http' : 'artifacts-only',
    comparisonSource:'current-process-environment',comparedValues:selected.values.filter(([,v]) => Buffer.byteLength(v)>=8).length,
    reviewedPublicExceptions:[...config.publicEnv].sort(),warnings:sorted(selected.warnings),targets};
  return {code,report:redact(report,selected.values)};
}
export async function main(args = process.argv.slice(2)) {
  let path: string | undefined, live = false;
  try {
    for (let i=0;i<args.length;i++) {
      if (args[i] === '--config' && !path && args[i+1]) path=args[++i];
      else if (args[i] === '--live' && !live) live=true;
      else throw Error();
    }
    if (!path) throw Error();
    const file=resolve(path), config=validateConfig(JSON.parse(await readFile(file,'utf8')));
    const result=await check(config,dirname(file),live);
    console.log(JSON.stringify(result.report,null,2)); process.exitCode=result.code;
  } catch {
    console.log(JSON.stringify({schemaVersion:1,exitCode:2,verdict:'incomplete',error:'Unable to validate or run the configured security checks. No raw configuration, exception or credential output was emitted.'}));
    process.exitCode=2;
  }
}
if (import.meta.main) await main();
