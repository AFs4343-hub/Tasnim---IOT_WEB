import {
  MapContainer,
  TileLayer,
  Marker,
  Popup,
  useMap
} from 'react-leaflet'

import L from 'leaflet'
import 'leaflet/dist/leaflet.css'
import { parseNodeCoords, resolveNodeCoords } from '../services/nodeCoordinates.js'


// ======================================================
// KOORDINAT NODE
// Isi lat/lng setelah lokasi final N0, N1, N2 diketahui.
// ======================================================

const locations = {
  N0: {
    label: 'Hulu / Baseline',
    lat: null,
    lng: null
  },

  N1: {
    label: 'Cabang Irigasi 1',
    lat: null,
    lng: null
  },

  N2: {
    label: 'Cabang Irigasi 2',
    lat: null,
    lng: null
  }
}


// Titik tampilan awal peta saja.
// BUKAN koordinat penelitian / node.
const FALLBACK_CENTER = [0.55, 123.15]


function createNodeIcon(node, status) {

  const dotColor =
    status === 'Online'
      ? '#34d399'
      : status === 'Offline'
      ? '#f87171'
      : '#94a3b8'


  return L.divIcon({
    className: '',
    html: `
      <div style="
        display:flex;
        align-items:center;
        gap:6px;
        padding:6px 9px;
        border-radius:10px;
        border:1px solid rgba(148,163,184,.28);
        background:#0f172a;
        color:#e2e8f0;
        box-shadow:0 8px 24px rgba(0,0,0,.28);
        font-family:system-ui,sans-serif;
        font-size:12px;
        font-weight:700;
        white-space:nowrap;
      ">
        <span style="
          display:block;
          width:8px;
          height:8px;
          border-radius:9999px;
          background:${dotColor};
        "></span>
        ${node}
      </div>
    `,
    iconSize: [74, 32],
    iconAnchor: [37, 16],
    popupAnchor: [0, -16]
  })
}


function FitMapToNodes({ validLocations }) {

  const map = useMap()


  if (validLocations.length === 0) {
    return null
  }


  const bounds =
    L.latLngBounds(
      validLocations.map(
        (item) => [
          item.lat,
          item.lng
        ]
      )
    )


  map.fitBounds(
    bounds,
    {
      padding: [50, 50],
      maxZoom: 18
    }
  )


  return null
}


const CONFIGURED_COORDS = parseNodeCoords(
  import.meta.env.VITE_TASNIM_NODE_COORDS
)


function NodeMap({ nodes }) {

  const mappedNodes =
    Object.entries(locations)
      .map(([nodeId, location]) => ({

        nodeId,

        ...location,

        ...resolveNodeCoords(nodeId, nodes?.[nodeId], CONFIGURED_COORDS),

        status:
          nodes?.[nodeId]?.status
          ?? 'Tidak Ada Data',

        ph:
          nodes?.[nodeId]?.ph
          ?? '—',

        tds:
          nodes?.[nodeId]?.tds
          ?? '—',

        turbidity:
          nodes?.[nodeId]?.turbidity
          ?? '—'

      }))


  const validLocations =
    mappedNodes.filter(
      (item) =>
        Number.isFinite(item.lat)
        && Number.isFinite(item.lng)
    )


  const allCoordinatesReady =
    validLocations.length === 3


  const mapCenter =
    validLocations.length > 0
      ? [
          validLocations[0].lat,
          validLocations[0].lng
        ]
      : FALLBACK_CENTER


  return (

    <div className="relative z-0 isolate overflow-hidden rounded-2xl border border-slate-800 bg-slate-900">


      {/* HEADER */}

      <div className="border-b border-slate-800 p-6">

        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">

          <div>

            <h2 className="text-xl font-bold">
              Peta Jaringan Node
            </h2>

            <p className="mt-1 text-sm text-slate-400">
              Peta interaktif posisi N0, N1, dan N2
              pada jaringan irigasi.
            </p>

          </div>


          <span
            className={`w-fit rounded-full border px-3 py-1 text-xs font-medium ${
              allCoordinatesReady
                ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                : 'border-amber-500/20 bg-amber-500/10 text-amber-300'
            }`}
          >

            {
              allCoordinatesReady
                ? 'Koordinat lengkap'
                : `${validLocations.length}/3 node dipetakan`
            }

          </span>

        </div>

      </div>



      {/* MAP + INFO */}

      <div className="grid gap-4 p-6 lg:grid-cols-[1.65fr_1fr]">


        {/* MAP SELALU DITAMPILKAN */}

        <div className="relative z-0 isolate overflow-hidden rounded-xl border border-slate-800 bg-slate-950">

          <MapContainer
            center={mapCenter}
            zoom={
              validLocations.length > 0
                ? 17
                : 11
            }
            scrollWheelZoom={true}
            className="relative z-0 h-[430px] w-full"
            style={{
              height: '430px',
              width: '100%'
            }}
          >

            <TileLayer
              attribution="&copy; OpenStreetMap contributors"
              url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
            />


            <FitMapToNodes
              validLocations={
                validLocations
              }
            />


            {
              validLocations.map(
                (item) => (

                  <Marker
                    key={item.nodeId}
                    position={[
                      item.lat,
                      item.lng
                    ]}
                    icon={
                      createNodeIcon(
                        item.nodeId,
                        item.status
                      )
                    }
                  >

                    <Popup>

                      <div>

                        <strong>
                          {item.nodeId}
                        </strong>

                        <div>
                          {item.label}
                        </div>

                        <div>
                          Status: {item.status}
                        </div>

                        <div>
                          pH: {item.ph}
                        </div>

                        <div>
                          TDS: {item.tds} ppm
                        </div>

                        <div>
                          Turbiditas: {item.turbidity} NTU
                        </div>

                      </div>

                    </Popup>

                  </Marker>

                )
              )
            }

          </MapContainer>


          {
            validLocations.length === 0 && (

              <div className="border-t border-slate-800 bg-slate-950 px-4 py-3">

                <p className="text-xs leading-5 text-slate-500">
                  Peta ini sudah interaktif dan dapat digeser
                  maupun di-zoom. Titik awal hanya digunakan
                  untuk menampilkan area peta; marker N0, N1,
                  dan N2 baru muncul setelah koordinat lapangan
                  dimasukkan.
                </p>

              </div>

            )
          }

        </div>



        {/* NODE INFO */}

        <div className="grid content-start gap-3">

          {
            mappedNodes.map(
              (item) => {

                const hasCoordinate =
                  Number.isFinite(item.lat)
                  && Number.isFinite(item.lng)


                return (

                  <div
                    key={item.nodeId}
                    className="rounded-xl border border-slate-800 bg-slate-950 p-4"
                  >

                    <div className="flex items-start justify-between gap-3">

                      <div>

                        <p className="text-lg font-bold text-white">
                          {item.nodeId}
                        </p>

                        <p className="mt-1 text-xs text-slate-500">
                          {item.label}
                        </p>

                      </div>


                      <span
                        className={`rounded-full border px-2.5 py-1 text-xs ${
                          hasCoordinate
                            ? 'border-emerald-500/20 bg-emerald-500/10 text-emerald-300'
                            : 'border-slate-700 bg-slate-800 text-slate-400'
                        }`}
                      >

                        {
                          hasCoordinate
                            ? 'Dipetakan'
                            : 'Belum dipetakan'
                        }

                      </span>

                    </div>


                    {
                      hasCoordinate
                        ? (

                          <div className="mt-4 text-xs text-slate-500">

                            <p>
                              Lat: {item.lat}
                            </p>

                            <p className="mt-1">
                              Lng: {item.lng}
                            </p>

                          </div>

                        )
                        : (

                          <p className="mt-4 text-xs leading-5 text-slate-500">
                            Isi VITE_TASNIM_NODE_COORDS di .env
                            (mis. N0:0.55,123.06) atau kirim latitude/longitude dari GPS alat.
                          </p>

                        )
                    }


                    <div className="mt-4 grid grid-cols-3 gap-2 text-center">

                      <div className="rounded-lg bg-slate-900 p-2">

                        <p className="text-[10px] text-slate-500">
                          pH
                        </p>

                        <p className="mt-1 text-sm font-semibold">
                          {item.ph}
                        </p>

                      </div>


                      <div className="rounded-lg bg-slate-900 p-2">

                        <p className="text-[10px] text-slate-500">
                          TDS
                        </p>

                        <p className="mt-1 text-sm font-semibold">
                          {item.tds}
                        </p>

                      </div>


                      <div className="rounded-lg bg-slate-900 p-2">

                        <p className="text-[10px] text-slate-500">
                          NTU
                        </p>

                        <p className="mt-1 text-sm font-semibold">
                          {item.turbidity}
                        </p>

                      </div>

                    </div>

                  </div>

                )

              }
            )
          }

        </div>


      </div>


    </div>

  )

}


export default NodeMap
