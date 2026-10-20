import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { run } from '../bin/frontend-security.mjs';

const root = fileURLToPath(new URL('../',import.meta.url));
test('security help does not require Bun or scan anything', () => {
  let text='';
  assert.equal(run({argv:['--help'],output:value => {text=value;},execute:() => {throw Error('must not execute');}}),0);
  assert.match(text,/--config/); assert.match(text,/No automatic fixes/);
});
test('caller-relative config is resolved before changing to trusted tool cwd', () => {
  let invocation;
  assert.equal(run({argv:['--config','policy.json','--live'],cwd:root,execute:(...args) => {invocation=args;return {status:0};}}),0);
  assert.equal(invocation[0],'bun');
  assert.deepEqual(invocation[1].slice(1),['--config',resolve(root,'policy.json'),'--live']);
  assert.equal(invocation[2].cwd,resolve(root,'tools/frontend-security'));
});
test('checker exit statuses are preserved', () => {
  for (const status of [0,1,2]) assert.equal(run({argv:['--config','policy.json'],execute:() => ({status})}),status);
});
test('invalid inputs and runtime failures never echo credential-bearing details', () => {
  const canary='synthetic-do-not-log-123456789';
  for (const argv of [[],['--unknown',canary],['--config','x','--config','y'],['--config','x','--live','--live'],['--config','--live']]) {
    const lines=[];
    assert.equal(run({argv,output:value => lines.push(value),execute:() => {throw Error(canary);}}),2);
    assert.equal(lines.join('').includes(canary),false); assert.equal(JSON.parse(lines[0]).verdict,'incomplete');
  }
  const lines=[];
  assert.equal(run({argv:['--config','x'],output:value => lines.push(value),execute:() => ({error:new Error(canary),status:null})}),2);
  assert.equal(lines.join('').includes(canary),false);
});
test('packaging keeps npx default installer and includes the independent checker', () => {
  const pkg=JSON.parse(readFileSync(new URL('../package.json',import.meta.url)));
  assert.equal(pkg.bin.harness,pkg.bin['harness-skills']);
  assert.equal(pkg.bin['frontend-security'],'bin/frontend-security.mjs');
  assert.ok(pkg.files.includes('tools/frontend-security/**'));
  assert.equal(pkg.dependencies,undefined);
});
