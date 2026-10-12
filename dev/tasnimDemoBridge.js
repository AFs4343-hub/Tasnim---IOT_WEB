// Private Codespaces demo bridge. NEVER instantiated for non-demo builds.
// Auth/password and RTDB requests go ONLY to two loopback Firebase emulators.
import { readFileSync } from 'node:fs'
import { normalizeSupervisorStatus } from '../src/services/operationalMonitorDemo.js'

const project = 'demo-tasnim-security'
const namespace = project + '-default-rtdb'
const authHost = '127.0.0.1:19004'
const dbHost = '127.0.0.1:19003'
const allowed = /^(admin|manager|viewer)@tasnim-auth-demo\.invalid$/

export function isDemoEnvironment(env) {
  return env.TASNIM_DEMO_LOGIN_MODE === 'YES'
    && env.VITE_TASNIM_DEMO_LOGIN === 'YES'
    && env.VITE_TASNIM_HARDWARE_V2_PREVIEW === 'YES'
    && env.GCLOUD_PROJECT === project
    && env.FIREBASE_AUTH_EMULATOR_HOST === authHost
    && env.FIREBASE_DATABASE_EMULATOR_HOST === dbHost
}

function verifyConfig() {
  const cfg = JSON.parse(readFileSync('tasnim.config.json', 'utf8'))
  const prod = JSON.parse(readFileSync('firebase.json', 'utf8'))
  const emulator = JSON.parse(readFileSync('firebase.emulator.security.json', 'utf8'))
  if (cfg.activeDataRoot !== 'simulation' || cfg.mode !== 'SIMULATION'
      || prod.database?.rules !== 'database.rules.json'
      || emulator.database?.rules !== 'database.hardware_test.v2.candidate.rules.json'
      || emulator.emulators?.auth?.host !== '127.0.0.1'
      || emulator.emulators?.auth?.port !== 19004
      || emulator.emulators?.database?.host !== '127.0.0.1'
      || emulator.emulators?.database?.port !== 19003) {
    throw Error('REFUSED: production or emulator configuration mismatch')
  }
}

const send = (res, code, data) => {
  res.statusCode = code
  res.setHeader('Content-Type', 'application/json; charset=utf-8')
  res.setHeader('Cache-Control', 'no-store')
  res.setHeader('X-Content-Type-Options', 'nosniff')
  res.end(JSON.stringify(data))
}
async function requestJson(req) {
  let body = ''
  for await (const buffer of req) {
    body += buffer.toString('utf8')
    if (body.length > 1024) throw Error('BAD_REQUEST')
  }
  return JSON.parse(body)
}
function claimRole(jwt) {
  try {
    const parts = jwt.split('.')
    if (parts.length !== 3) return null
    const data = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'))
    const role = data.tasnim_role
    return data.aud === project && ['admin','manager','viewer'].includes(role) ? role : null
  } catch { return null }
}
async function databaseRead(path, token, limit) {
  const url = new URL('http://' + dbHost + '/' + path + '.json')
  url.searchParams.set('ns', namespace)
  url.searchParams.set('auth', token)
  if (path === 'hardware_test/history') {
    url.searchParams.set('orderBy', '"$key"')
    url.searchParams.set('limitToLast', String(limit))
  }
  const response = await fetch(url, { signal: AbortSignal.timeout(8000), redirect: 'error' })
  if (!response.ok) throw Error([401,403].includes(response.status) ? 'DENIED' : 'UNAVAILABLE')
  const result = await response.json()
  if (result?.error) throw Error('DENIED')
  return result
}

export function createDemoBridgePlugin(env = process.env) {
  if (!isDemoEnvironment(env)) {
    if (env.TASNIM_DEMO_LOGIN_MODE === 'YES' || env.VITE_TASNIM_DEMO_LOGIN === 'YES')
      throw Error('REFUSED: incomplete browser-demo environment')
    return null
  }
  verifyConfig()
  return {
    name: 'tasnim-emulator-browser-demo-only', apply: 'serve',
    configureServer(server) {
      server.middlewares.use('/__tasnim_demo__', async (req, res, next) => {
        const path = req.url?.split('?')[0]
        if (!['/health','/login','/snapshot'].includes(path)) return next()
        try {
          if (req.headers.origin && new URL(req.headers.origin).host !== req.headers.host)
            return send(res, 403, { error: 'Cross-origin request denied' })
          if (path === '/health')
            return req.method === 'GET'
              ? send(res, 200, { demo: true, project, live: false })
              : send(res, 405, { error: 'Method denied' })
          if (path === '/login') {
            if (req.method !== 'POST') return send(res, 405, { error: 'Method denied' })
            if (!req.headers['content-type']?.startsWith('application/json'))
              return send(res, 415, { error: 'Expected JSON' })
            const payload = await requestJson(req)
            if (!allowed.test(payload?.email) || typeof payload.password !== 'string'
                || payload.password.length > 100)
              return send(res, 400, { error: 'Pilih akun demo yang terdaftar.' })
            const url = 'http://' + authHost
              + '/identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key=emulator-only'
            const response = await fetch(url, {
              method: 'POST', headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                email: payload.email, password: payload.password, returnSecureToken: true,
              }), signal: AbortSignal.timeout(8000), redirect: 'error',
            })
            if (!response.ok) return send(res, 401, { error: 'Email/sandi akun demo salah.' })
            const user = await response.json()
            const role = claimRole(user.idToken)
            if (!role) return send(res, 403, { error: 'Role demo tidak diizinkan.' })
            return send(res, 200, {
              token: user.idToken, role, expiresIn: Number(user.expiresIn) || 3600,
            })
          }
          if (req.method !== 'GET') return send(res, 405, { error: 'Method denied' })
          const token = /^Bearer ([A-Za-z0-9_.-]{50,4096})$/.exec(req.headers.authorization || '')?.[1]
          if (!token || !claimRole(token))
            return send(res, 401, { error: 'Login demo diperlukan.' })
          const count = Number.parseInt(new URL(req.url, 'http://localhost').searchParams.get('limit') || '60', 10)
          const limit = Math.max(1, Math.min(240, Number.isFinite(count) ? count : 60))
          try {
            const [nodes, history, analysis, operational_status] = await Promise.all([
              databaseRead('hardware_test/nodes', token, limit),
              databaseRead('hardware_test/history', token, limit),
              databaseRead('hardware_test/analysis/latest', token, limit),
              // Public feed is a sanitized copy only. Never expose
              // the private worker_state tree or privileged Admin API.
              databaseRead('hardware_test/operations/supervisor/latest', token, limit),
            ])
            return send(res, 200, {
              nodes, history, analysis,
              operational_status: normalizeSupervisorStatus(operational_status),
            })
          } catch (error) {
            if (error.message === 'DENIED')
              return send(res, 403, { error: 'Akses ditolak oleh Firebase Rules Emulator.' })
            throw error
          }
        } catch (error) {
          const bad = error instanceof SyntaxError || error.message === 'BAD_REQUEST'
          return send(res, bad ? 400 : 503, {
            error: bad ? 'Format permintaan tidak valid.' : 'Emulator belum siap atau tidak tersedia.',
          })
        }
      })
    },
  }
}
