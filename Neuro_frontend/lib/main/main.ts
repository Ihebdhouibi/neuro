import { app, BrowserWindow } from 'electron'
import { electronApp, optimizer } from '@electron-toolkit/utils'
import { initLogger } from './logger'
import log from './logger'
import { startPostgres, startBackend, stopServices } from './backend'
import { createAppWindow } from './app'

// Initialize file logging before anything else
initLogger()

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
// code. You can also put them in separate files and import them here.
