import assert from 'node:assert/strict';
import test from 'node:test';
import { patchPackagedElectronLoader, posixElectronWrapperContents } from './launch-from-spec.mjs';

test('packaged Electron wrapper preloads Playwright before Playwright flags', () => {
  const contents = posixElectronWrapperContents(
    '/tmp/Hermes App/Hermes',
    '/tmp/playwright/electron/loader.js',
  );

  assert.equal(
    contents,
    "#!/bin/sh\nexec '/tmp/Hermes App/Hermes' -r '/tmp/playwright/electron/loader.js' \"$@\"\n",
  );
  assert.ok(contents.indexOf(' -r ') < contents.indexOf(' "$@"'));
});

test('packaged loader keeps Playwright remote debugging active', () => {
  const stock = [
    "const { app } = require('electron');",
    'process.argv.splice(1, process.argv.indexOf("--remote-debugging-port=0"));',
    'app.whenReady();',
  ].join('\n');

  const patched = patchPackagedElectronLoader(stock);
  assert.match(patched, /const remoteDebugIndex = process\.argv\.indexOf\("--remote-debugging-port=0"\);/);
  assert.match(patched, /process\.argv\.splice\(1, remoteDebugIndex - 1\);/);
  assert.doesNotMatch(patched, /process\.argv\.splice\(1, process\.argv\.indexOf/);
});
