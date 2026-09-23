import assert from 'node:assert/strict';
import test from 'node:test';
import {
  loadElectronAfterPreparation,
  patchedPlaywrightElectronLoaderSource,
  patchedPlaywrightElectronSource,
  posixElectronWrapperContents,
} from './launch-from-spec.mjs';

test('uses Playwright upstream Electron 40 port setup', () => {
  assert.equal(
    patchedPlaywrightElectronSource(
      'let electronArguments = ["--inspect=0", "--remote-debugging-port=0", ...options.args || []];',
    ),
    'let electronArguments = ["--inspect=0", ...options.args || []];',
  );
  assert.equal(
    patchedPlaywrightElectronLoaderSource(
      'process.argv.splice(1, process.argv.indexOf("--remote-debugging-port=0"));',
    ),
    'process.argv.splice(1, process.argv.indexOf("--inspect=0"));\napp.commandLine.appendSwitch("remote-debugging-port", "0");',
  );
});

test('loads Playwright only after preparing its Electron driver', async () => {
  const events = [];
  const prepared = await loadElectronAfterPreparation(
    () => {
      events.push('prepare');
      return '/tmp/wrapper.sh';
    },
    async () => {
      events.push('import');
      return { _electron: { launch: async () => null } };
    },
  );

  assert.deepEqual(events, ['prepare', 'import']);
  assert.equal(prepared.wrapperPath, '/tmp/wrapper.sh');
});

test('preloads the patched loader before Playwright inspector arguments', () => {
  const wrapper = posixElectronWrapperContents('/tmp/Hermes', '/tmp/patched-loader.cjs');
  assert.equal(wrapper, '#!/bin/sh\nexec \'/tmp/Hermes\' -r \'/tmp/patched-loader.cjs\' "$@"\n');
});
