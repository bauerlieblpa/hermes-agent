import assert from 'node:assert/strict';
import test from 'node:test';
import { posixElectronWrapperContents } from './launch-from-spec.mjs';

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
