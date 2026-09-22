// Shared input setup for the install drivers. Only the selected app window
// is changed; helper windows retain their own coordinate system.
async function prepareWindowForInput(app, page) {
  // The install/update driver attaches over Chromium CDP to a real packaged
  // app. It intentionally has no Electron main-process handle; persist the
  // app-owned zoom setting and let the renderer apply it before clicking.
  const externalCdp = typeof app.browserWindow !== 'function'
  const window = externalCdp ? null : await app.browserWindow(page)
  // Use the same persistent setting as Appearance. A bare setZoomLevel is
  // overwritten by the app's focus/navigation handlers restoring saved zoom.
  const persistent = await page.evaluate(() => {
    const zoom = globalThis.hermesDesktop?.zoom
    if (!zoom?.setPercent || !zoom?.get) return false
    zoom.setPercent(100)
    return true
  })
  if (persistent) {
    // Playwright 1.58 treats an async waitForFunction predicate's Promise as
    // truthy even when it resolves false. Await each IPC read on the driver.
    const deadline = Date.now() + 15_000
    for (;;) {
      const state = await page.evaluate(() => {
        // Cold-start restoration can overwrite the first preference write.
        // Reapply through its owner until a subsequent read observes it.
        globalThis.hermesDesktop.zoom.setPercent(100)
        return globalThis.hermesDesktop.zoom.get()
      })
      if (externalCdp) {
        if (state.percent === 100) return
      } else {
        // The renderer IPC and BrowserWindow can observe different moments of
        // startup restoration. Both must agree before the driver sends input.
        const factor = await window.evaluate(win => win.webContents.getZoomFactor())
        if (state.percent === 100 && Math.abs(factor - 1) < 0.001) return
      }
      if (Date.now() >= deadline) {
        throw new Error(`timed out waiting for 100% app window zoom (IPC ${state.percent}%)`)
      }
      await page.waitForTimeout(100)
    }
  } else {
    // Older sampled releases have no zoom preference bridge. CDP-only mode
    // deliberately avoids a main-process injection, so it cannot set a native
    // BrowserWindow zoom level; the default is already 100% on a fresh profile.
    if (externalCdp) return
    await window.evaluate(win => win.webContents.setZoomLevel(0))
  }
  if (externalCdp) return
  // DPR includes OS display scaling; 100% page zoom is not always DPR 1.
  const factor = await window.evaluate(win => win.webContents.getZoomFactor())
  if (Math.abs(factor - 1) > 0.001) {
    throw new Error(`could not set app window zoom to 100% (factor ${factor})`)
  }
}

module.exports = { prepareWindowForInput }
