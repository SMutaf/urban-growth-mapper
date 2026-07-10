const LAYER_OPTIONS = [
  { key: 'heatmap', label: 'Isı Haritası' },
  { key: 'projects', label: 'Projeler (Yol, Demiryolu, OSB, Liman)' },
  { key: 'busStops', label: 'Otobüs Durakları (2600+ nokta)' },
  { key: 'schools', label: 'Okullar (683 nokta)' },
  { key: 'otherPois', label: 'Diğer Noktalar (Hastane, Şehir Merkezi)' },
]

export default function LayerControlPanel({ layers, onToggleLayer }) {
  return (
    <div className="layer-panel">
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
