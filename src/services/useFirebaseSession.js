import { useEffect, useState } from 'react'
import {
  connectAuthEmulator, getAuth, onAuthStateChanged, signInAnonymously,
} from 'firebase/auth'
import { firebaseApp } from './firebase'

// Rules hardware_test saat ini: ".read": "auth != null".
// Supaya website bisa dibuka TANPA form login, browser membuat sesi
// Firebase anonim secara otomatis (Firebase Console → Authentication →
// Sign-in method → Anonymous harus diaktifkan). Website tetap read-only.
// Set VITE_TASNIM_ANON_AUTH=NO untuk mematikan perilaku ini.
export const ANON_AUTH_ENABLED = import.meta.env.VITE_TASNIM_ANON_AUTH !== 'NO'

// Uji lokal dengan Firebase Auth Emulator (opsional, hanya jika di-set):
// VITE_FIREBASE_AUTH_EMULATOR_HOST=127.0.0.1:9099
const AUTH_EMULATOR_HOST = import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_HOST
let authInstance = null

function tasnimAuth() {
  if (!authInstance) {
    authInstance = getAuth(firebaseApp)
    if (AUTH_EMULATOR_HOST) {
      connectAuthEmulator(authInstance, `http://${AUTH_EMULATOR_HOST}`, { disableWarnings: true })
    }
  }
  return authInstance
}

const IDLE = Object.freeze({ status: 'idle', uid: null, anonymous: false, errorCode: null })
const CHECKING = Object.freeze({ status: 'checking', uid: null, anonymous: false, errorCode: null })

export function useFirebaseSession(enabled) {
  const [session, setSession] = useState(CHECKING)

  useEffect(() => {
    if (!enabled) return undefined
    let cancelled = false
    let attempted = false
    let auth
    try {
      auth = tasnimAuth()
    } catch (error) {
      // Mis. VITE_FIREBASE_API_KEY kosong: jangan buat seluruh halaman crash.
      queueMicrotask(() => {
        if (!cancelled) setSession({ ...IDLE, status: 'signed_out', errorCode: error?.code ?? 'unknown' })
      })
      return () => { cancelled = true }
    }
    const unsubscribe = onAuthStateChanged(auth, user => {
      if (cancelled) return
      if (user) {
        setSession({
          status: 'signed_in', uid: user.uid,
          anonymous: user.isAnonymous, errorCode: null,
        })
        return
      }
      if (!ANON_AUTH_ENABLED || attempted) {
        setSession(prev => prev.status === 'signed_out' ? prev
          : { ...IDLE, status: 'signed_out' })
        return
      }
      attempted = true
      signInAnonymously(auth).catch(error => {
        if (!cancelled) {
          setSession({ ...IDLE, status: 'signed_out', errorCode: error?.code ?? 'unknown' })
        }
      })
    })
    return () => {
      cancelled = true
      unsubscribe()
    }
  }, [enabled])

  return enabled ? session : IDLE
}

// Pesan untuk pengguna jika Firebase menolak pembacaan hardware_test.
export function permissionHelp(session) {
  const code = session?.errorCode
  if (code === 'auth/operation-not-allowed' || code === 'auth/admin-restricted-operation') {
    return 'Login anonim belum diaktifkan di proyek Firebase. Aktifkan di Firebase Console → Authentication → Sign-in method → Anonymous, lalu muat ulang halaman. Alternatif: buka file CSV/JSON dari tombol di atas.'
  }
  if (code === 'auth/network-request-failed') {
    return 'Tidak bisa menghubungi Firebase Authentication. Periksa koneksi internet lalu muat ulang.'
  }
  if (code === 'auth/invalid-api-key' || code === 'auth/api-key-not-valid.-please-pass-a-valid-api-key.') {
    return 'VITE_FIREBASE_API_KEY di file .env tidak valid untuk proyek ini.'
  }
  if (!ANON_AUTH_ENABLED) {
    return 'Login anonim dimatikan (VITE_TASNIM_ANON_AUTH=NO). Hapus pengaturan itu atau izinkan baca hardware_test di Rules.'
  }
  if (session?.status === 'signed_in') {
    return 'Sesi Firebase sudah aktif, tetapi Rules tetap menolak baca hardware_test. Periksa Realtime Database Rules proyek.'
  }
  return 'Firebase menolak akses hardware_test tanpa autentikasi. Aktifkan login Anonymous di Firebase Console atau buka file CSV/JSON dari tombol di atas.'
}
