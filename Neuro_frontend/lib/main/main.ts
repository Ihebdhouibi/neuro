import { app, BrowserWindow } from 'electron'
import { electronApp, optimizer } from '@electron-toolkit/utils'
import { initLogger } from './logger'
import log from './logger'
import { startPostgres, startBackend, stopServices } from './backend'
import { createAppWindow } from './app'

// Initialize file logging before anything else
initLogger()

// Single-instance lock — prevents two NeuroX windows from racing for port 7861
// (the bundled FastAPI backend) and stepping on each other's PostgreSQL.
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  log.info('Another NeuroX instance is already running — exiting this one')
  app.quit()
} else {
  app.on('second-instance', () => {
    // Focus the existing window if user double-clicks the launcher again.
    const wins = BrowserWindow.getAllWindows()
    if (wins.length > 0) {
      const win = wins[0]
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  app.whenReady().then(async () => {
    electronApp.setAppUserModelId('com.electron')

    // Start services (PostgreSQL → Backend) before creating the window
    log.info('Starting backend services...')
    await startPostgres()
    await startBackend()

    log.info('Application ready — creating main window')
    createAppWindow()

    app.on('browser-window-created', (_, window) => {
      optimizer.watchWindowShortcuts(window)
    })

    app.on('activate', function () {
      if (BrowserWindow.getAllWindows().length === 0) {
        createAppWindow()
      }
    })
  })

  app.on('before-quit', () => {
    log.info('Application quitting — stopping services')
    stopServices()
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
      app.quit()
    }
  })
}
// code. You can also put them in separate files and import them here.
