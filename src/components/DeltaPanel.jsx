function DeltaValue({ label, value, unit = '' }) {
  const formattedValue =
    value > 0 ? `+${value}` : `${value}`

  return (
    <div className="rounded-xl bg-slate-950 p-4">
      <p className="text-xs text-slate-500">
        {label}
      </p>

      <p className="mt-2 text-2xl font-bold text-cyan-400">
        {formattedValue}
      </p>

      {unit && (
        <p className="text-xs text-slate-500">
          {unit}
        </p>
      )}
    </div>
  )
}

function DeltaPanel({
  title,
  upstream,
  downstream
}) {
  const deltaPh =
    (downstream.ph - upstream.ph).toFixed(2)

  const deltaTds =
    (downstream.tds - upstream.tds).toFixed(0)

  const deltaTurbidity =
    (downstream.turbidity - upstream.turbidity).toFixed(0)

  return (
    <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">

      <div className="mb-5">
        <p className="text-sm text-slate-400">
          Perubahan Antar-Node
        </p>

        <h3 className="mt-1 text-xl font-bold">
          {title}
        </h3>

        <p className="mt-1 text-xs text-slate-500">
          ΔX = X hilir − X hulu
        </p>
      </div>

      <div className="grid grid-cols-3 gap-3">

        <DeltaValue
          label="Δ pH"
          value={deltaPh}
        />

        <DeltaValue
          label="Δ TDS"
          value={deltaTds}
          unit="ppm"
        />

        <DeltaValue
          label="Δ Turbiditas"
          value={deltaTurbidity}
          unit="NTU"
        />

      </div>

    </div>
  )
}

export default DeltaPanel