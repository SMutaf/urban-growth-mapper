import { useMemo, useState } from 'react'

const PROJECT_TYPE_LABELS = {
  highway: 'Otoban / Devlet Yolu',
  railway: 'Demiryolu',
}

// Unlike DistrictPanel (which fetches one district's boundary on select),
// roadFeatures is already the full FeatureCollection fetched once by App -
// selecting a road just picks the matching feature out of it, no extra
// network round-trip needed.
export default function RoadSearchPanel({ roadFeatures, selectedRoadName, onSelectRoad }) {
  const [query, setQuery] = useState('')

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('tr-TR')
    if (!normalized) return roadFeatures
    return roadFeatures.filter((f) => f.properties.name.toLocaleLowerCase('tr-TR').includes(normalized))
  }, [roadFeatures, query])

  return (
    <div className="road-search-panel">
      <input
        type="text"
        className="road-search-panel-search"
        placeholder="Yol / demiryolu ara..."
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <ul className="road-search-panel-list">
        {filtered.map((feature) => (
          <li key={feature.properties.name}>
            <button
              className={feature.properties.name === selectedRoadName ? 'active' : ''}
              onClick={() => onSelectRoad(feature)}
            >
              {feature.properties.name}
              <span className="road-search-panel-type">
                {PROJECT_TYPE_LABELS[feature.properties.project_type] || feature.properties.project_type}
              </span>
            </button>
          </li>
        ))}
        {filtered.length === 0 && <li className="road-search-panel-empty">Sonuç bulunamadı</li>}
      </ul>
    </div>
  )
}
