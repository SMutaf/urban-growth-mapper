import L from 'leaflet'

// Category -> map-marker badges: a colored circular badge with a white
// monochrome glyph, matching the same outline-icon visual language as
// components/icons.jsx (used for UI chrome) - built as raw SVG strings
// here instead of React components because Leaflet's L.divIcon takes an
// HTML string, not JSX.
const ICON_PATHS = {
  school: '<path d="M2 9.5 12 5l10 4.5-10 4.5L2 9.5Z"/><path d="M6 11.5V17c0 1.1 2.7 2.5 6 2.5s6-1.4 6-2.5v-5.5"/><line x1="21" y1="9.5" x2="21" y2="16"/>',
  university: '<path d="M12 6c-1.5-1-4-1.5-6-1v13c2 0 4.5.5 6 1.5 1.5-1 4-1.5 6-1.5V5c-2-.5-4.5 0-6 1Z"/><line x1="12" y1="6" x2="12" y2="19.5"/>',
  hospital: '<rect x="3" y="4" width="18" height="17" rx="1.5"/><line x1="12" y1="9" x2="12" y2="15"/><line x1="9" y1="12" x2="15" y2="12"/>',
  bus_stop: '<rect x="3" y="5" width="18" height="12" rx="2"/><line x1="3" y1="11" x2="21" y2="11"/><circle cx="7.5" cy="19" r="1.5"/><circle cx="16.5" cy="19" r="1.5"/>',
  train_station: '<rect x="7" y="3" width="10" height="12" rx="4"/><line x1="7" y1="10" x2="17" y2="10"/><line x1="9.5" y1="15" x2="7.5" y2="20"/><line x1="14.5" y1="15" x2="16.5" y2="20"/>',
  metro_station: '<rect x="7" y="3" width="10" height="12" rx="4"/><line x1="7" y1="10" x2="17" y2="10"/><circle cx="10" cy="7" r="0.1"/><circle cx="14" cy="7" r="0.1"/><line x1="9.5" y1="15" x2="7.5" y2="20"/><line x1="14.5" y1="15" x2="16.5" y2="20"/>',
  // Two roads forking/merging - reads as an actual junction, not just an X.
  highway_junction: '<path d="M12 21V13"/><path d="M12 13L5 4"/><path d="M12 13L19 4"/>',
  shopping_center: '<path d="M6 8h12l-1 12H7L6 8Z"/><path d="M9 8V6a3 3 0 0 1 6 0v2"/>',
  city_center: '<path d="M12 2l2.9 6.3 6.9.6-5.2 4.7 1.6 6.8L12 16.9 5.8 20.4l1.6-6.8L2.2 8.9l6.9-.6L12 2Z"/>',
  prison: '<rect x="4" y="3" width="16" height="18" rx="1"/><line x1="8" y1="3" x2="8" y2="21"/><line x1="12" y1="3" x2="12" y2="21"/><line x1="16" y1="3" x2="16" y2="21"/>',
  landfill: '<path d="M5 7h14l-1.2 13a2 2 0 0 1-2 1.8H8.2a2 2 0 0 1-2-1.8L5 7Z"/><line x1="3" y1="7" x2="21" y2="7"/><path d="M9 7V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v3"/>',
  // Neutral headstone silhouette, not a religious symbol - cemeteries in
  // this dataset aren't all one denomination.
  cemetery: '<path d="M7 21V11a5 5 0 0 1 10 0v10"/><line x1="5" y1="21" x2="19" y2="21"/>',
  industrial_zone: '<path d="M3 21V10l5 3V10l5 3V10l5 3v8H3Z"/><line x1="3" y1="21" x2="21" y2="21"/>',
  port: '<circle cx="12" cy="5" r="2"/><line x1="12" y1="7" x2="12" y2="21"/><path d="M5 12a7 7 0 0 0 14 0"/><line x1="5" y1="12" x2="5" y2="9"/><line x1="19" y1="12" x2="19" y2="9"/>',
  other: '<circle cx="12" cy="12" r="4"/>',
}

const CATEGORY_COLORS = {
  school: '#2563eb',
  university: '#0891b2',
  hospital: '#dc2626',
  bus_stop: '#0f766e',
  train_station: '#4338ca',
  metro_station: '#7c3aed',
  highway_junction: '#ea580c',
  shopping_center: '#db2777',
  city_center: '#d97706',
  prison: '#4b5563',
  landfill: '#78716c',
  cemetery: '#64748b',
  industrial_zone: '#c2410c',
  port: '#1e3a8a',
  other: '#6b7280',
}

const BADGE_SIZE = 26
const GENERIC_BADGE_SIZE = 22

function buildDivIcon(category, { generic = false } = {}) {
  const path = ICON_PATHS[category] || ICON_PATHS.other
  const color = CATEGORY_COLORS[category] || CATEGORY_COLORS.other
  const size = generic ? GENERIC_BADGE_SIZE : BADGE_SIZE
  const iconSize = generic ? 12 : 14
  const opacity = generic ? 0.55 : 1

  const html = `
    <div style="
      width:${size}px; height:${size}px; border-radius:50%;
      background:${color}; opacity:${opacity};
      display:flex; align-items:center; justify-content:center;
      box-shadow:0 1px 4px rgba(0,0,0,0.45); border:2px solid white;
    ">
      <svg width="${iconSize}" height="${iconSize}" viewBox="0 0 24 24" fill="none"
        stroke="white" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        ${path}
      </svg>
    </div>`

  return L.divIcon({
    html,
    className: 'category-marker-icon',
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -size / 2],
  })
}

// Small cache - the same category's icon HTML is identical every time, no
// need to rebuild/re-parse it for every one of thousands of POI markers.
const _cache = new Map()

export function categoryMarkerIcon(category, options) {
  const key = `${category}:${options?.generic ? 'g' : 'n'}`
  if (!_cache.has(key)) {
    _cache.set(key, buildDivIcon(category, options))
  }
  return _cache.get(key)
}
