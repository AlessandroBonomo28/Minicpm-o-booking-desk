import { mkdir, rm } from 'node:fs/promises';
import { spawnSync } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const appRoot = resolve(here, '..');
const outDir = resolve(appRoot, 'out');
const target = resolve(appRoot, '..', 'static', 'docs');

await rm(target, { recursive: true, force: true });
await mkdir(target, { recursive: true });

const result = spawnSync('cp', ['-R', `${outDir}/.`, target], {
  stdio: 'inherit',
});
if (result.status !== 0) {
  throw new Error(`Failed to copy docs static output: cp exited with ${result.status}`);
}

console.log(`Published docs to ${target}`);
