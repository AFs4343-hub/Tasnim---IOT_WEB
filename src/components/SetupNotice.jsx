// Ditampilkan jika konfigurasi Firebase belum ada atau website gagal start.
export default function SetupNotice({ missing = [], error = null }) {
  return (
    <main className="min-h-screen bg-slate-950 px-6 py-12 text-white">
      <div className="mx-auto max-w-2xl rounded-2xl border border-amber-500/40 bg-slate-900 p-6">
        <p className="text-sm font-semibold tracking-widest text-cyan-400">TAS[N]IM</p>
        <h1 className="mt-2 text-2xl font-bold">
          {missing.length ? 'Konfigurasi Firebase belum lengkap' : 'Website gagal dimulai'}
        </h1>
        {missing.length > 0 && <>
          <p className="mt-3 text-sm text-slate-300">Nilai berikut kosong di <code>.env.local</code>:</p>
          <ul className="mt-2 list-disc pl-6 text-sm text-amber-200">
            {missing.map(key => <li key={key}><code>{key}</code></li>)}
          </ul>
        </>}
        {error && <p className="mt-3 rounded-lg bg-slate-950 p-3 font-mono text-xs text-rose-300">{String(error?.message ?? error)}</p>}
        <p className="mt-4 text-sm text-slate-300">Cara memperbaiki di terminal Codespaces:</p>
        <pre className="mt-2 overflow-x-auto rounded-lg bg-slate-950 p-3 text-xs text-slate-200">bash scripts/setup_tasnim.sh</pre>
        <p className="mt-3 text-xs text-slate-500">
          Skrip mengambil konfigurasi web dari proyek Firebase lalu menulis <code>.env.local</code>.
          Setelah itu hentikan <code>npm run dev</code> (Ctrl+C) dan jalankan lagi — Vite hanya membaca .env saat start.
        </p>
      </div>
    </main>
  )
}
