import { afterEach, expect, test } from 'bun:test';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { check, validateConfig } from '../scripts/check';

const roots: string[]=[];
afterEach(async () => { await Promise.all(roots.splice(0).map(root => rm(root,{recursive:true,force:true}))); });
async function temp() { const root=await mkdtemp(join(tmpdir(),'security-cli-')); roots.push(root); return root; }
function config(root: string) {
  return validateConfig({version:1,maxFileMiB:1,timeoutMs:1000,compareEnv:[],publicEnv:[],targets:[{name:'test',root}]});
}

test('strict configuration rejects unknown keys, duplicate names and unsafe origins', () => {
  const base=config('/some/build');
  for (const input of [{...base,version:2},{...base,autoFix:true},{...base,targets:[...base.targets,...base.targets]},
    {...base,maxFileMiB:0},{...base,targets:[{name:'bad',root:'/build',origin:'https://user:password@example.invalid'}]},
    {...base,targets:[{name:'bad',root:'/build',origin:'https://example.invalid/?token=never-send'}]}]) expect(() => validateConfig(input)).toThrow();
});

test('identical explicit inputs produce identical reports with no timestamps or AI decisions', async () => {
  const root=await temp(); await writeFile(join(root,'z.json'),'{}'); await writeFile(join(root,'a.json'),'{}');
  const first=await check(config(root),root,false,{}), second=await check(config(root),root,false,{});
  expect(first.code).toBe(0); expect(JSON.stringify(first.report)).toBe(JSON.stringify(second.report));
  expect((first.report as any).verdict).toBe('passed');
});

test('private artifacts fail and missing build roots are incomplete, never clean', async () => {
  const root=await temp(); await writeFile(join(root,'.env.production'),'PUBLIC_ID=synthetic');
  expect((await check(config(root),root,false,{})).code).toBe(1);
  expect((await check(config(join(root,'missing')),root,false,{})).code).toBe(2);
});

test('required comparison names fail closed when unavailable and values are redacted', async () => {
  const root=await temp(), value='synthetic-private-cli-canary-123456789';
  const cfg={...config(root),compareEnv:['TEST_PRIVATE_TOKEN']};
  await writeFile(join(root,value+'.json'),JSON.stringify({key:value}));
  expect((await check(cfg,root,false,{})).code).toBe(2);
  const found=await check(cfg,root,false,{TEST_PRIVATE_TOKEN:value});
  expect(found.code).toBe(1); expect(JSON.stringify(found.report)).not.toContain(value);
});

test('HTTP checks run only with explicit live mode', async () => {
  const root=await temp(); await writeFile(join(root,'index.html'),'<!doctype html><title>Test</title>');
  let requests=0;
  const server=Bun.serve({hostname:'127.0.0.1',port:0,fetch() { requests++; return new Response(null,{status:404}); }});
  try {
    const cfg={...config(root),targets:[{name:'test',root,origin:server.url.origin}]};
    expect((await check(cfg,root,false,{})).code).toBe(0); expect(requests).toBe(0);
    expect((await check(cfg,root,true,{})).code).toBe(0); expect(requests).toBe(9);
  } finally { server.stop(true); }
});

test('live mode without a configured origin is explicitly incomplete', async () => {
  const root=await temp(); expect((await check(config(root),root,true,{})).code).toBe(2);
});

test('CLI configuration failures are JSON, nonzero and never dump contents', async () => {
  const root=await temp(), value='synthetic-never-log-config-canary';
  const path=join(root,'config.json'); await writeFile(path,JSON.stringify({password:value}));
  const child=Bun.spawn([process.execPath,new URL('../scripts/check.ts',import.meta.url).pathname,'--config',path],{
    cwd:new URL('../',import.meta.url).pathname,stdout:'pipe',stderr:'pipe',env:{PATH:process.env.PATH!,HOME:process.env.HOME!}});
  const [code,stdout,stderr]=await Promise.all([child.exited,new Response(child.stdout).text(),new Response(child.stderr).text()]);
  expect(code).toBe(2); expect(stderr).toBe(''); expect(stdout).not.toContain(value);
  expect(JSON.parse(stdout).verdict).toBe('incomplete');
});
