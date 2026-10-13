import { computeTransmissionStats, NODE_IDS } from '../services/iotMetrics.js'


function getSignalQuality(rssi) {
  if (rssi === null || rssi === undefined || Number.isNaN(Number(rssi))) {
    return { label: 'Belum Ada Data', className: 'text-slate-500' }
  }
  const value = Number(rssi)
  if (value >= -60) return { label: 'Baik', className: 'text-emerald-400' }
  if (value >= -70) return { label: 'Cukup', className: 'text-cyan-400' }
  if (value >= -80) return { label: 'Lemah', className: 'text-amber-400' }
  return { label: 'Sangat Lemah', className: 'text-red-400' }
}


function MetricCard({ title, value, unit, note, tone = 'text-white' }) {
  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
      <p className="text-xs text-slate-500">{title}</p>
      <div className="mt-2 flex items-end gap-1">
        <p className={`text-2xl font-semibold ${tone}`}>{value}</p>
        {unit && <span className="mb-1 text-sm text-slate-500">{unit}</span>}
      </div>
      {note && <p className="mt-2 text-xs leading-5 text-slate-500">{note}</p>}
    </div>
  )
}


function SignalCard({ nodeId, node, transmission }) {
  const hasRSSI = node?.rssi !== null && node?.rssi !== undefined
    && !Number.isNaN(Number(node.rssi))
  const quality = getSignalQuality(hasRSSI ? node.rssi : null)
  const pct = transmission?.successPct

  return (
    <div className="rounded-xl border border-slate-800 bg-slate-950 p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-xs text-slate-500">{nodeId}</p>
          <p className="mt-1 text-sm font-medium text-slate-300">Koneksi Wi-Fi</p>
        </div>
        <span className={`text-xs font-semibold ${quality.className}`}>{quality.label}</span>
      </div>

      <div className="mt-4 flex items-end gap-1">
        <p className="text-2xl font-semibold text-white">{hasRSSI ? Number(node.rssi) : '—'}</p>
        {hasRSSI && <span className="mb-1 text-sm text-slate-500">dBm</span>}
      </div>

      {transmission && (
        <div className="mt-3">
          <div className="flex justify-between text-xs text-slate-500">
            <span>Kelengkapan slot</span>
            <span className="text-slate-300">
              {transmission.received}/{transmission.expected}
              {pct != null && ` (${pct.toFixed(0)}%)`}
            </span>
          </div>
          <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-800">
            <div
              className={`h-full rounded-full ${pct >= 90 ? 'bg-emerald-400' : pct >= 70 ? 'bg-amber-400' : 'bg-red-400'}`}
              style={{ width: `${Math.min(100, pct ?? 0)}%` }}
            />
          </div>
        </div>
      )}

      <p className="mt-3 border-t border-slate-800 pt-3 text-xs text-slate-500">
        Sequence terakhir:{' '}
        <span className="text-slate-300">{node?.sequence ?? '—'}</span>
      </p>
    </div>
  )
}


function IoTPerformancePanel({ nodes, history = [], intervalMinutes = 5 }) {
  const nodeList = nodes ? Object.values(nodes) : []
  const onlineCount = nodeList.filter(node => node.status === 'Online').length
  const offlineCount = nodeList.filter(node => node.status === 'Offline').length
  const noDataCount = nodeList.filter(node => node.status === 'Tidak Ada Data').length

  const stats = computeTransmissionStats(history)
  const slotMode = stats?.mode === 'SLOT_5_MIN'
  const successTone = stats?.successPct == null ? 'text-white'
    : stats.successPct >= 90 ? 'text-emerald-400'
      : stats.successPct >= 70 ? 'text-amber-400' : 'text-red-400'

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      <div className="mb-6">
        <h2 className="text-xl font-bold">Kinerja Sistem IoT</h2>
        <p className="mt-1 text-sm text-slate-400">
          Konektivitas node dan evaluasi transmisi dari history yang sedang dimuat.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard title="Node Online" value={onlineCount} unit="/ 3"
          note="Berdasarkan timestamp data terakhir (≤ 10 menit)." />
        <MetricCard title="Node Offline" value={offlineCount} unit="/ 3"
          note="Node yang melewati batas waktu pengiriman." />
        <MetricCard title="Belum Ada Data" value={nodes ? noDataCount : 3} unit="/ 3"
          note="Node yang belum memiliki timestamp pengiriman." />
        <MetricCard title="History Dimuat" value={history.length}
          note={`Jumlah slot waktu yang sedang dimuat. Interval target ${intervalMinutes} menit.`} />
      </div>

      <div className="mt-6">
        <p className="text-sm font-semibold text-slate-300">Kualitas Sinyal Wi-Fi &amp; Kelengkapan</p>
        <p className="mt-1 text-xs text-slate-500">
          RSSI dari koneksi Wi-Fi tiap ESP32; kelengkapan = slot 5 menit yang terisi node tersebut.
        </p>
        <div className="mt-3 grid gap-4 md:grid-cols-3">
          {NODE_IDS.map(nodeId => (
            <SignalCard key={nodeId} nodeId={nodeId} node={nodes?.[nodeId]}
              transmission={stats?.perNode?.[nodeId]} />
          ))}
        </div>
      </div>

      <div className="mt-6">
        <p className="mb-3 text-sm font-semibold text-slate-300">Evaluasi Transmisi</p>
        <div className="grid gap-4 md:grid-cols-3">
          <MetricCard
            title="Transmission Success"
            value={stats?.successPct != null ? stats.successPct.toFixed(1) : '—'}
            unit={stats?.successPct != null ? '%' : undefined}
            tone={successTone}
            note={stats
              ? `${stats.totalReceived} dari ${stats.totalExpected} ${slotMode ? 'slot-node' : 'record-node'} diterima dalam ${stats.sessions} sesi.`
              : 'Menunggu history pengukuran.'}
          />
          <MetricCard
            title="Data Loss"
            value={stats?.lossPct != null ? stats.lossPct.toFixed(1) : '—'}
            unit={stats?.lossPct != null ? '%' : undefined}
            note={stats
              ? `${stats.totalExpected - stats.totalReceived} slot-node kosong; ${stats.completeSlots} slot lengkap N0+N1+N2.`
              : 'Dihitung dari slot 5 menit yang tidak terisi.'}
          />
          <MetricCard
            title="Latency"
            value="—"
            note="Butuh waktu kirim & waktu terima di paket; firmware saat ini hanya mengirim waktu ukur."
          />
        </div>
      </div>

      <div className="mt-6 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
        <p className="text-sm font-medium text-cyan-400">Cara membaca</p>
        <p className="mt-1 text-xs leading-5 text-slate-400">
          Sesi dipisah bila jeda antar slot lebih dari 15 menit (mis. antar hari),
          sehingga jam di luar sesi pengukuran tidak dihitung sebagai data hilang.
          Nilai dihitung dari history yang sedang dimuat — muat lebih banyak di panel
          Riwayat untuk mencakup seluruh sesi.
        </p>
      </div>

    </div>
  )
}

export default IoTPerformancePanel
