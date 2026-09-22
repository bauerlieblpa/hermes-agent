import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import test from 'node:test';
import { packagedResourcesPath, stagePackagedResources } from './launch-from-spec.mjs';

test('resolves packaged resource locations for Linux and macOS bundles', () => {
  assert.equal(
    packagedResourcesPath('/tmp/Hermes'),
    '/tmp/resources',
  );
  assert.equal(
    packagedResourcesPath('/tmp/Hermes.app/Contents/MacOS/Hermes', 'darwin'),
    '/tmp/Hermes.app/Contents/Resources',
  );
});

test('stages every packaged resource into Playwright Electron resources', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'hermes-e2e-stage-'));
  const source = path.join(root, 'source');
  const target = path.join(root, 'target');
  fs.mkdirSync(path.join(source, 'app.asar.unpacked'), { recursive: true });
  fs.writeFileSync(path.join(source, 'app.asar'), 'app');
  fs.writeFileSync(path.join(source, 'install-stamp.json'), '{}');
  fs.writeFileSync(path.join(source, 'app.asar.unpacked', 'native.node'), 'native');
  fs.mkdirSync(target, { recursive: true });
  fs.writeFileSync(path.join(target, 'default_app.asar'), 'driver');

  stagePackagedResources(source, target);

  for (const name of ['app.asar', 'app.asar.unpacked', 'install-stamp.json']) {
    assert.ok(fs.lstatSync(path.join(target, name)).isSymbolicLink(), `${name} should be linked`);
  }
  assert.equal(fs.readFileSync(path.join(target, 'app.asar'), 'utf8'), 'app');
  fs.rmSync(root, { recursive: true, force: true });
});
