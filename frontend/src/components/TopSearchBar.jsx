import { useMemo, useState } from 'react'
import { BusIcon, HospitalIcon, MenuIcon, SchoolIcon, SearchIcon } from './icons.jsx'

const MAX_RESULTS = 8

const QUICK_LAYERS = [
  { key: 'schools', label: 'Okullar', Icon: SchoolIcon },
  { key: 'hospitals', label: 'Hastaneler', Icon: HospitalIcon },
  { key: 'busStops', label: 'Otobüs Durakları', Icon: BusIcon },
]

const RESULT_TYPE_LABELS = {
  district: 'İlçe',
  road: 'Yol/Demiryolu',
  school: 'Okul',
  hospital: 'Hastane',
}

// Combines districts/roads/schools/hospitals (already-loaded, small
// datasets - see App.jsx) into one flat searchable list. Bus stops are
// deliberately excluded (2600+ points, mostly identically-named
// "Otobus Duragi" - see MapView.jsx's GENERIC_POI_NAMES - not useful to
// search by name; they're quick-toggle only, see QUICK_LAYERS above).
function buildSearchIndex(districts, roadFeatures, searchablePois) {
  const index = []
  districts.forEach((d) => index.push({ type: 'district', name: d.name, data: d }))
  roadFeatures.forEach((f) => index.push({ type: 'road', name: f.properties.name, data: f }))
  searchablePois.forEach((poi) =>
    index.push({ type: poi.category, name: poi.name, data: poi }),
  )
  return index
}

export default function TopSearchBar({
  districts,
  roadFeatures,
  searchablePois,
  layers,
  onToggleLayer,
  onSelectResult,
  onToggleMenu,
}) {
  const [query, setQuery] = useState('')

  const searchIndex = useMemo(
    () => buildSearchIndex(districts, roadFeatures, searchablePois),
    [districts, roadFeatures, searchablePois],
  )

  const results = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase('tr-TR')
    if (!normalized) return []
    return searchIndex
      .filter((item) => item.name.toLocaleLowerCase('tr-TR').includes(normalized))
      .slice(0, MAX_RESULTS)
  }, [searchIndex, query])

  const handleSelect = (result) => {
    onSelectResult(result)
    setQuery('')
  }

  return (
    <div className="top-bar-row">
      <button className="icon-pill-button" onClick={onToggleMenu} aria-label="Menü">
        <MenuIcon />
      </button>

      <div className="search-pill-wrapper">
        <div className="search-pill">
          <span className="search-pill-icon">
            <SearchIcon />
          </span>
          <input
            type="text"
            className="search-pill-input"
            placeholder="Haritada ara (ilçe, okul, hastane, yol...)"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        {results.length > 0 && (
          <ul className="search-results-dropdown">
            {results.map((result) => (
              <li key={`${result.type}-${result.name}`}>
                <button onClick={() => handleSelect(result)}>
                  <span className="search-results-name">{result.name}</span>
                  <span className="search-results-type">
                    {RESULT_TYPE_LABELS[result.type] || result.type}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      {QUICK_LAYERS.map((option) => (
        <button
          key={option.key}
          className={`chip-pill-button ${layers[option.key] ? 'active' : ''}`}
          onClick={() => onToggleLayer(option.key)}
        >
          <option.Icon />
          {option.label}
        </button>
      ))}
    </div>
  )
}
