import log from 'electron-log/main'
import { app } from 'electron'
import { join } from 'path'

/**
 * Initialize file logging for the main process.
 * Logs are stored in {installDir}/logs/ (or NEUROX_LOG_DIR if set).
 */
export function initLogger(): void {
  const logDir =
    process.env['NEUROX_LOG_DIR'] ||
    (app.isPackaged ? join(app.getPath('exe'), '..', 'logs') : join(app.getAppPath(), '..', 'logs'))

  log.transports.file.resolvePathFn = () => join(logDir, 'frontend.log')
  log.transports.file.maxSize = 10 * 1024 * 1024 // 10 MB
  log.transports.file.format = '{y}-{m}-{d} {h}:{i}:{s}.{ms} | {level} | {text}'
  log.transports.console.level = 'info'
  log.transports.file.level = 'debug'

  // Redirect all console.log/warn/error to electron-log
  log.initialize()

  log.info(`Frontend log directory: ${logDir}`)
  log.info(`App packaged: ${app.isPackaged}`)
}

export default log
