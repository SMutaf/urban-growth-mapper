import { useMemo, useState } from 'react'

const numberFormatter = new Intl.NumberFormat('tr-TR')
const percentFormatter = new Intl.NumberFormat('tr-TR', {
  style: 'percent',
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export default function DistrictPanel({ districts, selectedDistrict, onSelectDistrict }) {
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('tr-TR')
    if (!normalized) return districts
    return districts.filter((d) => d.name.toLocaleLowerCase('tr-TR').includes(normalized))
  }, [districts, query])

  return (
    <div className="district-panel">
      <input
        type="text"
        className="district-panel-search"
        placeholder="İlçe ara..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
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

      <ul className="district-list">
        {filtered.map((d) => (
          <li key={d.name}>
            <button
              className={d.name === selectedDistrict?.name ? 'active' : ''}
              onClick={() => onSelectDistrict(d)}
            >
              {d.name}
            </button>
          </li>
        ))}
        {filtered.length === 0 && <li className="district-list-empty">Sonuç bulunamadı</li>}
      </ul>
    </div>
  )
}
