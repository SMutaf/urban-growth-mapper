import { useMemo, useState } from 'react'
import { CloseIcon } from './icons.jsx'

const numberFormatter = new Intl.NumberFormat('tr-TR')
const percentFormatter = new Intl.NumberFormat('tr-TR', {
  style: 'percent',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

const LAND_USE_PROFILE_OPTIONS = [
  { value: 'balanced', label: 'Dengeli (varsayılan)' },
  { value: 'residential', label: 'Konut' },
  { value: 'commercial', label: 'Ticari' },
  { value: 'industrial', label: 'Sanayi / Lojistik' },
]

// Schools/hospitals/bus stops have their own quick-toggle chips in
// TopSearchBar - not repeated here, see App.jsx's layers state. Every other
// POI category gets its own checkbox (see MapView.jsx's
// CATEGORY_LAYER_KEYS) instead of one shared "diğer noktalar" catch-all.
const LAYER_OPTIONS = [
  { key: 'heatmap', label: 'Isı Haritası' },
  { key: 'projects', label: 'Projeler (OSB, Liman)' },
  { key: 'roads', label: 'Yollar (Otoban/Devlet Yolu, çizgi)' },
  { key: 'railways', label: 'Demiryolları (çizgi)' },
  { key: 'universities', label: 'Üniversiteler' },
  { key: 'highwayJunctions', label: 'Otoyol Kavşakları' },
  { key: 'metroStations', label: 'Metro İstasyonları' },
  { key: 'trainStations', label: 'Tren İstasyonları' },
  { key: 'shoppingCenters', label: 'Çarşı / AVM' },
  { key: 'cityCenters', label: 'Şehir Merkezi' },
  { key: 'cemeteries', label: 'Mezarlıklar' },
  { key: 'prisons', label: 'Cezaevleri' },
  { key: 'landfills', label: 'Çöp Sahaları' },
]

export default function FilterDrawer({
  isOpen,
  onClose,
  districts,
  selectedDistrict,
  onSelectDistrict,
  onOpenDistrictDetail,
  layers,
  onToggleLayer,
  landUseProfile,
  onChangeLandUseProfile,
  minScore,
  onChangeMinScore,
}) {
  const [districtQuery, setDistrictQuery] = useState('')

  const filteredDistricts = useMemo(() => {
    const normalized = districtQuery.trim().toLocaleLowerCase('tr-TR')
    if (!normalized) return districts
    return districts.filter((d) => d.name.toLocaleLowerCase('tr-TR').includes(normalized))
  }, [districts, districtQuery])

  if (!isOpen) return null

  return (
    <div className="filter-drawer">
      <div className="filter-drawer-header">
        <span>Menü</span>
        <button className="filter-drawer-close" onClick={onClose} aria-label="Kapat">
          <CloseIcon />
        </button>
      </div>

      <div className="filter-drawer-section-title">İlçe Seçimi</div>
      <input
        type="text"
        className="filter-drawer-search"
        placeholder="İlçe ara..."
        value={districtQuery}
        onChange={(e) => setDistrictQuery(e.target.value)}
      />

      {selectedDistrict && (
        <div className="district-info-card">
          <div className="district-info-title">{selectedDistrict.name}</div>
          <div className="district-info-row">
            <span>Nüfus ({selectedDistrict.population_year})</span>
            <strong>{numberFormatter.format(selectedDistrict.population)}</strong>
          </div>
          <div className="district-info-row">
            <span>Yıllık büyüme</span>
            <strong className={selectedDistrict.growth_rate >= 0 ? 'positive' : 'negative'}>
              {selectedDistrict.growth_rate >= 0 ? '+' : ''}
              {percentFormatter.format(selectedDistrict.growth_rate)}
            </strong>
          </div>
        </div>
      )}

      <ul className="filter-drawer-district-list">
        {filteredDistricts.map((d) => (
          <li key={d.name} className="filter-drawer-district-row">
            <button
              className={d.name === selectedDistrict?.name ? 'active' : ''}
              onClick={() => onSelectDistrict(d)}
            >
              {d.name}
            </button>
            <button className="filter-drawer-district-detail-button" onClick={() => onOpenDistrictDetail(d)}>
              Detay
            </button>
          </li>
        ))}
        {filteredDistricts.length === 0 && (
          <li className="filter-drawer-district-empty">Sonuç bulunamadı</li>
        )}
      </ul>

      <div className="filter-drawer-section-title">Detaylı Filtreleme</div>

      <label className="filter-drawer-label">Kullanım Amacı</label>
      <select
        className="filter-drawer-select"
        value={landUseProfile}
        onChange={(event) => onChangeLandUseProfile(event.target.value)}
      >
        {LAND_USE_PROFILE_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>

      <label className="filter-drawer-label">
        Minimum Büyüme Skoru: {minScore.toFixed(2)}
      </label>
      <input
        type="range"
        className="filter-drawer-range"
        min="0"
        max="1"
        step="0.05"
        value={minScore}
        onChange={(event) => onChangeMinScore(Number(event.target.value))}
      />

      {LAYER_OPTIONS.map((option) => (
        <label key={option.key} className="filter-drawer-option">
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
