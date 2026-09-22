import assert from 'node:assert/strict';
import test from 'node:test';
import { externalCdpArgs } from './launch-from-spec.mjs';

test('external CDP launch adds an ephemeral remote debugging port once', () => {
  assert.deepEqual(externalCdpArgs(['--foo']), ['--foo', '--remote-debugging-port=0']);
  assert.deepEqual(
    externalCdpArgs(['--remote-debugging-port=9222', '--foo']),
    ['--remote-debugging-port=9222', '--foo'],
  );
});
