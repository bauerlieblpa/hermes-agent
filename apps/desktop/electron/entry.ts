import { app } from 'electron'

import { wslgLaunchArgs } from './wslg-launch'
import { spawnWslgLaunch } from './wslg-launch-process'

const args = wslgLaunchArgs(process.argv.slice(1), process.env, process.platform)
const e2eLaunchTrace = process.env.HERMES_E2E_LAUNCH_TRACE === '1'

if (e2eLaunchTrace) {
  console.log(`[hermes:e2e-launch] entry: ${args ? 'WSLg handoff' : 'importing main'}`)
}

if (args) {
  // Keep the launcher alive until the child exits: npm's concurrently must not
  // tear down Vite during this handoff. No backend, windows or single-instance
  // lock are created in this parent. The child has an explicit platform flag,
  // so it goes straight into main on its first pass.
  const child = spawnWslgLaunch(args)

  child.once('error', error => {
    console.error('[hermes] WSLg launch failed:', error)
    app.exit(1)
  })
  child.once('exit', code => app.exit(code ?? 1))

  for (const signal of ['SIGINT', 'SIGTERM'] as const) {
    process.once(signal, () => child.kill(signal))
  }
} else {
  await import('./main')

  if (e2eLaunchTrace) {
    console.log('[hermes:e2e-launch] entry: main module evaluated')
  }
}
