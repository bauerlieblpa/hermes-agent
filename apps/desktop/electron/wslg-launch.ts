import { detectRemoteDisplay, isWslEnvironment } from './bootstrap-platform'

// Ozone is selected before application JavaScript. Never appendSwitch here:
// that leaves the browser on X11 while GPU children receive Wayland.
export function wslgLaunchArgs(
  argv: readonly string[],
  env: NodeJS.ProcessEnv,
  platform: NodeJS.Platform,
  isWsl = isWslEnvironment(env, platform)
): string[] | null {
  const displayEnv = { ...env, HERMES_DESKTOP_DISABLE_GPU: undefined }

  if (platform !== 'linux' || !isWsl || !env.WAYLAND_DISPLAY || detectRemoteDisplay({ env: displayEnv, platform })) {
    return null
  }

  if (argv.some(arg => arg === '--ozone-platform' || arg.startsWith('--ozone-platform='))) {
    return null
  }

  const hintArg = argv.findLast(arg => arg.startsWith('--ozone-platform-hint='))
  const hint = hintArg?.split('=')[1] ?? env.ELECTRON_OZONE_PLATFORM_HINT
  const backend = hint === 'x11' ? 'x11' : 'wayland'

  return [...argv, `--ozone-platform=${backend}`]
}

/**
 * Carry an already-bound Node inspector endpoint across the WSLg supervisor
 * hand-off.  Electron's Playwright launcher deliberately passes `--inspect=0`;
 * that makes the parent choose a random port.  Re-spawning that literal flag
 * makes the child choose a *different* random port after the parent releases
 * its inspector, leaving Playwright attached to the inert supervisor.
 */
export function forwardBoundInspectorArg(argv: readonly string[], inspectorUrl: string | undefined): string[] {
  if (!inspectorUrl) {
    return [...argv]
  }

  let host: string

  try {
    host = new URL(inspectorUrl).host
  } catch {
    return [...argv]
  }

  return argv.map(arg => {
    if (arg === '--inspect' || arg.startsWith('--inspect=')) {
      return `--inspect=${host}`
    }

    if (arg === '--inspect-brk' || arg.startsWith('--inspect-brk=')) {
      return `--inspect-brk=${host}`
    }

    return arg
  })
}
