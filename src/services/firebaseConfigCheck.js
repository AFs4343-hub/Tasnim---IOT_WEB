// Nilai .env minimum agar Firebase web SDK bisa dimulai.
const REQUIRED = ['VITE_FIREBASE_API_KEY', 'VITE_FIREBASE_DATABASE_URL', 'VITE_FIREBASE_PROJECT_ID']

export function missingFirebaseConfig(env = {}) {
  return REQUIRED.filter(key => !String(env[key] ?? '').trim())
}
