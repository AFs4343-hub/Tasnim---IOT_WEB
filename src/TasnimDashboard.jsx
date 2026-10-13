import { useState } from 'react'
import App from './App.jsx'
import DataSourceBar from './components/DataSourceBar.jsx'
import {
  SOURCE_HARDWARE, readStoredDataSource, resolveInitialDataSource, storeDataSource,
} from './services/dataSource.js'
import { loadLocalHardwareFiles } from './services/sdCsv.js'

// Dashboard utama: pilih Data Alat (Firebase hardware_test), Simulasi,
// atau file CSV microSD / ekspor JSON lokal. Tanpa form login; website
// hanya MEMBACA. File lokal tidak pernah diunggah.
export default function TasnimDashboard() {
  const [source, setSource] = useState(() => resolveInitialDataSource({
    env: import.meta.env,
    stored: readStoredDataSource(),
  }))
  const [localFile, setLocalFile] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const changeSource = next => {
    storeDataSource(next)
    setSource(next)
    setLocalFile(null)
    setError('')
  }

  const openFiles = async files => {
    setLoading(true)
    setError('')
    try {
      setLocalFile(await loadLocalHardwareFiles(files))
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Gagal membaca file.')
    } finally {
      setLoading(false)
    }
  }

  // key memaksa App mulai bersih ketika sumber berganti, sehingga data
  // simulasi tidak pernah tercampur dengan data alat.
  const appKey = localFile ? `file:${localFile.fileNames.join('|')}` : source

  return (
    <div className="min-h-screen bg-slate-950 text-white">
      <DataSourceBar
        source={source}
        onSourceChange={changeSource}
        localFile={localFile}
        onOpenFiles={openFiles}
        onCloseFile={() => { setLocalFile(null); setError('') }}
        loading={loading}
        error={error}
      />
      <App
        key={appKey}
        dataSource={localFile ? SOURCE_HARDWARE : source}
        fieldSnapshot={localFile ?? undefined}
      />
    </div>
  )
}
