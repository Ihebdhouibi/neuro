import { ChildProcess, spawn } from 'child_process'
import { join } from 'path'
import { app } from 'electron'
import { existsSync } from 'fs'
import log from './logger'

let backendProcess: ChildProcess | null = null

/** Resolve the installation root (where backend/, pgsql/, python/ live) */
function getInstallDir(): string {
  if (app.isPackaged) {
    // In production the exe is at {installDir}/frontend/ElectronReactApp.exe
    return join(app.getPath('exe'), '..', '..')
  }
  // In development, project root is one level up from Neuro_frontend
  return join(app.getAppPath(), '..')
}

/**
 * Start the bundled PostgreSQL server.
 * Expects: {installDir}/pgsql/bin/pg_ctl.exe and {installDir}/pgsql/data/
 */
export async function startPostgres(): Promise<void> {
  const installDir = getInstallDir()
  const pgCtl = join(installDir, 'pgsql', 'bin', 'pg_ctl.exe')
  const programData = process.env.ProgramData || process.env.PROGRAMDATA || 'C:\\ProgramData'
  const dataDir = process.env.NEUROX_PG_DATA || join(programData, 'NeuroX', 'pgdata17')

  if (!existsSync(pgCtl)) {
    log.warn(`PostgreSQL not found at ${pgCtl} — skipping (using system PostgreSQL or dev setup)`)
    return
  }

  // Defensive cleanup: if a previous app crash left a postmaster.pid file
  // behind, pg_ctl start will refuse to launch with "lock file already
  // exists". Use `pg_ctl status` to check if the server really is running;
  // exit code 3 means "not running" — in that case the .pid is stale and
  // safe to delete. If PG is already running (code 0), skip starting.
  const pidFile = join(dataDir, 'postmaster.pid')
  let alreadyRunning = false
  if (existsSync(pidFile)) {
    log.info(`Found existing postmaster.pid at ${pidFile} — checking if PG is actually running`)
    try {
      const status = spawn(pgCtl, ['status', '-D', dataDir], {
        stdio: 'ignore',
        windowsHide: true,
      })
      await new Promise<void>((res) => {
        status.on('close', (code) => {
          // pg_ctl status exit codes: 0 = running, 3 = not running,
          // 4 = no/invalid data dir. Only treat 3 as "safe to delete pid".
          if (code === 0) {
            log.info('PostgreSQL is already running — skipping start')
            alreadyRunning = true
          } else if (code === 3) {
            try {
              require('fs').unlinkSync(pidFile)
              log.info('Removed stale postmaster.pid')
            } catch (e) {
              log.warn(`Could not remove stale postmaster.pid: ${(e as Error).message}`)
            }
          } else {
            log.warn(`pg_ctl status returned unexpected code ${code} — not touching postmaster.pid`)
          }
          res()
        })
        status.on('error', () => res())
      })
    } catch (e) {
      log.warn(`pg_ctl status check failed: ${(e as Error).message}`)
    }
  }

  if (alreadyRunning) {
    return
  }

  log.info(`Starting PostgreSQL: ${pgCtl} -D ${dataDir}`)

  return new Promise((resolve) => {
    const proc = spawn(pgCtl, ['start', '-D', dataDir, '-w', '-l', join(installDir, 'logs', 'postgresql.log')], {
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    })

    let stdout = ''
    let stderr = ''
    proc.stdout?.on('data', (d) => { stdout += d.toString() })
    proc.stderr?.on('data', (d) => { stderr += d.toString() })

    proc.on('close', (code) => {
      if (code === 0) {
        log.info('PostgreSQL started successfully')
        resolve()
      } else {
        log.error(`PostgreSQL failed to start (exit ${code}): ${stderr || stdout}`)
        // Don't reject — app can still run if PostgreSQL is already running or user has system install
        resolve()
      }
    })
    proc.on('error', (err) => {
      log.error(`Failed to spawn pg_ctl: ${err.message}`)
      resolve() // non-fatal
    })
  })
}

/**
 * Start the Python FastAPI backend.
 * Looks for a PyInstaller-bundled exe first, then falls back to Python + source.
 */
export async function startBackend(): Promise<void> {
  const installDir = getInstallDir()

  // Option 1: PyInstaller-built backend exe
  const backendExe = join(installDir, 'backend', 'neurox_backend.exe')
  // Option 2: Embedded Python running source (installed layout: backend_src/)
  const pythonExe = join(installDir, 'python', 'python.exe')
  const backendScriptInstalled = join(installDir, 'backend_src', 'api', 'main_paddleocr.py')
  // Option 3: Dev venv (dev layout: Neuro_backend/)
  const devPython = join(installDir, 'Neuro_backend', 'venv', 'Scripts', 'python.exe')
  const backendScriptDev = join(installDir, 'Neuro_backend', 'api', 'main_paddleocr.py')

  let cmd: string
  let args: string[]
  const env: Record<string, string> = {
    ...process.env as Record<string, string>,
    NEUROX_LOG_DIR: join(installDir, 'logs'),
    DATABASE_URL: process.env.DATABASE_URL || 'postgresql://postgres@localhost:5432/neurox',
    PADDLEX_HOME: join(installDir, 'models'),
    PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK: 'True',
  }

  // Add PaddleOCR DLL directory to PATH so libpaddle.pyd can load dependencies
  const paddleDllPath = join(installDir, 'python', 'Lib', 'site-packages', 'paddle', 'libs')
  if (existsSync(paddleDllPath)) {
    const pathKey = Object.keys(env).find((key) => key.toLowerCase() === 'path') || 'PATH'
    env[pathKey] = `${paddleDllPath};${env[pathKey] || ''}`
    log.info(`Added PaddleOCR DLL path to ${pathKey}: ${paddleDllPath}`)
  }

  if (existsSync(backendExe)) {
    cmd = backendExe
    args = []
    log.info(`Starting backend (bundled exe): ${cmd}`)
  } else if (existsSync(pythonExe) && existsSync(backendScriptInstalled)) {
    cmd = pythonExe
    args = [backendScriptInstalled]
    log.info(`Starting backend (embedded python): ${cmd} ${args.join(' ')}`)
  } else if (existsSync(devPython) && existsSync(backendScriptDev)) {
    cmd = devPython
    args = [backendScriptDev]
    log.info(`Starting backend (dev venv): ${cmd} ${args.join(' ')}`)
  } else {
    log.warn('No backend executable found — backend must be started manually')
    log.warn(`Searched: ${backendExe}, ${pythonExe} + ${backendScriptInstalled}, ${devPython} + ${backendScriptDev}`)
    return
  }

  backendProcess = spawn(cmd, args, {
    stdio: ['ignore', 'pipe', 'pipe'],
    windowsHide: true,
    env,
  })

  backendProcess.stdout?.on('data', (data) => {
    log.info(`[backend] ${data.toString().trimEnd()}`)
  })
  backendProcess.stderr?.on('data', (data) => {
    log.warn(`[backend] ${data.toString().trimEnd()}`)
  })
  backendProcess.on('error', (err) => {
    log.error(`Backend process error: ${err.message}`)
  })
  backendProcess.on('close', (code) => {
    log.info(`Backend process exited with code ${code}`)
    backendProcess = null
  })

  // Wait for the backend to be reachable
  await waitForBackend()
}

/** Poll the /health endpoint until the backend responds (max ~15 seconds) */
async function waitForBackend(maxRetries = 30, interval = 500): Promise<void> {
  const { net } = await import('electron')
  const url = 'http://127.0.0.1:7861/'

  for (let i = 0; i < maxRetries; i++) {
    try {
      const ok = await new Promise<boolean>((resolve) => {
        const req = net.request({ method: 'GET', url })
        req.on('response', () => resolve(true))
        req.on('error', () => resolve(false))
        req.end()
        setTimeout(() => resolve(false), 1000)
      })
      if (ok) {
        log.info('Backend is ready')
        return
      }
    } catch {
      // ignore
    }
    await new Promise((r) => setTimeout(r, interval))
    if ((i + 1) % 5 === 0) log.info(`Waiting for backend... (${i + 1}/${maxRetries})`)
  }
  log.warn('Backend did not become ready within timeout — app will load anyway')
}

/** Gracefully stop backend and PostgreSQL */
export function stopServices(): void {
  if (backendProcess && !backendProcess.killed) {
    log.info('Stopping backend process...')
    backendProcess.kill('SIGTERM')
    // On Windows SIGTERM may not work — force kill after 3s
    setTimeout(() => {
      if (backendProcess && !backendProcess.killed) {
        log.warn('Force-killing backend process')
        backendProcess.kill('SIGKILL')
      }
    }, 3000)
  }

  // Stop PostgreSQL gracefully
  const installDir = getInstallDir()
  const pgCtl = join(installDir, 'pgsql', 'bin', 'pg_ctl.exe')
  const programData = process.env.ProgramData || process.env.PROGRAMDATA || 'C:\\ProgramData'
  const dataDir = process.env.NEUROX_PG_DATA || join(programData, 'NeuroX', 'pgdata17')

  if (existsSync(pgCtl)) {
    log.info('Stopping PostgreSQL...')
    const proc = spawn(pgCtl, ['stop', '-D', dataDir, '-m', 'fast'], {
      stdio: 'ignore',
      windowsHide: true,
    })
    proc.on('close', (code) => {
      log.info(`PostgreSQL stopped (exit ${code})`)
    })
  }
}
