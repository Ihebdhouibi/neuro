import { ChildProcess, spawn } from 'child_process'
import { join } from 'path'
import { app } from 'electron'
import { existsSync } from 'fs'
import log from './logger'

let pgProcess: ChildProcess | null = null
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
  const dataDir = join(installDir, 'pgsql', 'data')

  if (!existsSync(pgCtl)) {
    log.warn(`PostgreSQL not found at ${pgCtl} — skipping (using system PostgreSQL or dev setup)`)
    return
  }

  log.info(`Starting PostgreSQL: ${pgCtl} -D ${dataDir}`)

  return new Promise((resolve, reject) => {
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
  // Option 2: Embedded Python running source
  const pythonExe = join(installDir, 'python', 'python.exe')
  const backendScript = join(installDir, 'Neuro_backend', 'api', 'main_paddleocr.py')
  // Option 3: Dev venv
  const devPython = join(installDir, 'Neuro_backend', 'venv', 'Scripts', 'python.exe')

  let cmd: string
  let args: string[]
  const env = { ...process.env, NEUROX_LOG_DIR: join(installDir, 'logs') }

  if (existsSync(backendExe)) {
    cmd = backendExe
    args = []
    log.info(`Starting backend (bundled exe): ${cmd}`)
  } else if (existsSync(pythonExe) && existsSync(backendScript)) {
    cmd = pythonExe
    args = [backendScript]
    log.info(`Starting backend (embedded python): ${cmd} ${args.join(' ')}`)
  } else if (existsSync(devPython) && existsSync(backendScript)) {
    cmd = devPython
    args = [backendScript]
    log.info(`Starting backend (dev venv): ${cmd} ${args.join(' ')}`)
  } else {
    log.warn('No backend executable found — backend must be started manually')
    log.warn(`Searched: ${backendExe}, ${pythonExe}, ${devPython}`)
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
  const dataDir = join(installDir, 'pgsql', 'data')

  if (existsSync(pgCtl)) {
    log.info('Stopping PostgreSQL...')
    const proc = spawn(pgCtl, ['stop', '-D', dataDir, '-m', 'fast'], {
      stdio: 'ignore',
      windowsHide: true,
    })
    proc.on('close', (code) => {
      log.info(`PostgreSQL stopped (exit ${code})`)
    })
    pgProcess = null
  }
}
