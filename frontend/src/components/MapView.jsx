import L from 'leaflet'
import 'leaflet.heat'
import 'leaflet.markercluster'
import { useEffect, useRef } from 'react'

const PROJECT_TYPE_LABELS = {
  highway: 'Otoban',
  railway: 'YHT / Demiryolu',
  industrial_zone: 'Organize Sanayi Bölgesi',
  port: 'Liman',
  other: 'Diğer',
}

const POI_CATEGORY_LABELS = {
  metro_station: 'Metro İstasyonu',
  train_station: 'Tren İstasyonu',
  highway_junction: 'Otoyol Kavşağı',
  university: 'Üniversite',
  bus_stop: 'Otobüs Durağı/Terminali',
  hospital: 'Hastane',
  shopping_center: 'Çarşı / AVM',
  school: 'Okul',
  city_center: 'Şehir Merkezi',
  other: 'Diğer',
}

// Names osm_feature_parser.py falls back to when OSM had no `name` tag for
// a bus stop/station - these are lower-confidence (unverified) entries and
// get a visually distinct (grey, hollow) marker instead of solid teal.
const GENERIC_POI_NAMES = new Set(['Otobus Duragi', 'Otobus Terminali'])

function poiPopupHtml(poi, isGeneric) {
  return `<strong>${poi.name}</strong><br/>${POI_CATEGORY_LABELS[poi.category] || poi.category}${
    isGeneric ? '<br/><em>OSM\'de isim etiketi yok - konum dogrulanmali</em>' : ''
  }`
}

function poiCircleMarker(poi) {
  const isGeneric = GENERIC_POI_NAMES.has(poi.name)
  return L.circleMarker([poi.latitude, poi.longitude], {
    radius: 7,
    color: isGeneric ? '#9ca3af' : '#0f766e',
    fillColor: isGeneric ? '#e5e7eb' : '#14b8a6',
    fillOpacity: isGeneric ? 0.5 : 0.9,
    weight: 2,
  })
    .bindTooltip(isGeneric ? `${poi.name} (isim dogrulanmadi)` : poi.name, {
      direction: 'top',
      sticky: true,
    })
    .bindPopup(poiPopupHtml(poi, isGeneric))
}

export default function MapView({
  projects,
  pointsOfInterest = [],
  heatmapPoints,
  center,
  highlightedBoundary,
  layers,
}) {
  const mapContainerRef = useRef(null)
  const mapRef = useRef(null)
  const heatLayerRef = useRef(null)
  const markersLayerRef = useRef(null)
  const busStopLayerRef = useRef(null)
  const schoolLayerRef = useRef(null)
  const otherPoiLayerRef = useRef(null)
  const boundaryLayerRef = useRef(null)

  useEffect(() => {
    if (mapRef.current) return
    const map = L.map(mapContainerRef.current).setView(center, 12)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap katkıda bulunanlar',
    }).addTo(map)
    markersLayerRef.current = L.layerGroup()
    busStopLayerRef.current = L.markerClusterGroup({ maxClusterRadius: 50 })
    schoolLayerRef.current = L.markerClusterGroup({ maxClusterRadius: 50 })
    otherPoiLayerRef.current = L.layerGroup()
    boundaryLayerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Heatmap: data + visibility
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current)
      heatLayerRef.current = null
    }
    if (layers.heatmap && heatmapPoints && heatmapPoints.length > 0) {
      const heatData = heatmapPoints.map((p) => [p.center_lat, p.center_lon, p.score])
      heatLayerRef.current = L.heatLayer(heatData, { radius: 35, blur: 25, maxZoom: 14 }).addTo(map)
    }
  }, [heatmapPoints, layers.heatmap])

  // Projects: populate markers
  useEffect(() => {
    const layerGroup = markersLayerRef.current
    if (!layerGroup) return
    layerGroup.clearLayers()
    projects.forEach((project) => {
      L.marker([project.latitude, project.longitude])
        .bindTooltip(project.name, { direction: 'top', sticky: true })
        .bindPopup(
          `<strong>${project.name}</strong><br/>${
            PROJECT_TYPE_LABELS[project.project_type] || project.project_type
          }<br/>${project.status}`,
        )
        .addTo(layerGroup)
    })
  }, [projects])

  // Projects: visibility
  useEffect(() => {
    const map = mapRef.current
    const layerGroup = markersLayerRef.current
    if (!map || !layerGroup) return
    if (layers.projects) {
      map.addLayer(layerGroup)
    } else {
      map.removeLayer(layerGroup)
    }
  }, [layers.projects])

  // POIs: split into bus stops / schools / other, populate each group
  useEffect(() => {
    const busStopGroup = busStopLayerRef.current
    const schoolGroup = schoolLayerRef.current
    const otherGroup = otherPoiLayerRef.current
    if (!busStopGroup || !schoolGroup || !otherGroup) return
    busStopGroup.clearLayers()
    schoolGroup.clearLayers()
    otherGroup.clearLayers()
    pointsOfInterest.forEach((poi) => {
      const marker = poiCircleMarker(poi)
      if (poi.category === 'bus_stop') {
        busStopGroup.addLayer(marker)
      } else if (poi.category === 'school') {
        schoolGroup.addLayer(marker)
      } else {
        marker.addTo(otherGroup)
      }
    })
  }, [pointsOfInterest])

  // POIs: visibility (bus stops, schools, and other POIs toggle independently)
  useEffect(() => {
    const map = mapRef.current
    const busStopGroup = busStopLayerRef.current
    if (!map || !busStopGroup) return
    if (layers.busStops) {
      map.addLayer(busStopGroup)
    } else {
      map.removeLayer(busStopGroup)
    }
  }, [layers.busStops])

  useEffect(() => {
    const map = mapRef.current
    const schoolGroup = schoolLayerRef.current
    if (!map || !schoolGroup) return
    if (layers.schools) {
      map.addLayer(schoolGroup)
    } else {
      map.removeLayer(schoolGroup)
    }
  }, [layers.schools])

  useEffect(() => {
    const map = mapRef.current
    const otherGroup = otherPoiLayerRef.current
    if (!map || !otherGroup) return
    if (layers.otherPois) {
      map.addLayer(otherGroup)
    } else {
      map.removeLayer(otherGroup)
    }
  }, [layers.otherPois])

  useEffect(() => {
    const map = mapRef.current
    const layerGroup = boundaryLayerRef.current
    if (!map || !layerGroup) return
    layerGroup.clearLayers()
    if (!highlightedBoundary) return

    const geoJsonLayer = L.geoJSON(highlightedBoundary, {
      style: { color: '#dc2626', weight: 2, fillColor: '#f87171', fillOpacity: 0.15 },
    })
    geoJsonLayer.addTo(layerGroup)
    const bounds = geoJsonLayer.getBounds()
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40] })
    }
  }, [highlightedBoundary])

  return <div ref={mapContainerRef} style={{ height: '100vh', width: '100%' }} />
}
