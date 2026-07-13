const LAYER_OPTIONS = [
  { key: 'heatmap', label: 'Isı Haritası' },
  { key: 'projects', label: 'Projeler (OSB, Liman)' },
  { key: 'roads', label: 'Yollar (Otoban/Devlet Yolu, çizgi)' },
  { key: 'railways', label: 'Demiryolları (çizgi)' },
  { key: 'busStops', label: 'Otobüs Durakları (2600+ nokta)' },
  { key: 'schools', label: 'Okullar (683 nokta)' },
  { key: 'otherPois', label: 'Diğer Noktalar (Hastane, Tren İstasyonu, Üniversite, Kavşak vb.)' },
]

const LAND_USE_PROFILE_OPTIONS = [
  { value: 'balanced', label: 'Dengeli (varsayılan)' },
  { value: 'residential', label: 'Konut' },
  { value: 'commercial', label: 'Ticari' },
  { value: 'industrial', label: 'Sanayi / Lojistik' },
]

export default function LayerControlPanel({
  layers,
  onToggleLayer,
  landUseProfile,
  onChangeLandUseProfile,
}) {
  return (
    <div className="layer-panel">
      <div className="layer-panel-title">Kullanım Amacı</div>
      <select
        className="layer-panel-select"
        value={landUseProfile}
        onChange={(event) => onChangeLandUseProfile(event.target.value)}
      >
        {LAND_USE_PROFILE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <div className="layer-panel-title">Katmanlar</div>
      {LAYER_OPTIONS.map((option) => (
        <label key={option.key} className="layer-panel-option">
          <input
            type="checkbox"
            checked={layers[option.key]}
            onChange={() => onToggleLayer(option.key)}
          />
          {option.label}
        </label>
      ))}
    </div>
  )
}
