import L from 'leaflet'
import 'leaflet.markercluster'
import { useEffect, useRef } from 'react'
import { buildHeatmapRaster } from '../heatmapRaster.js'
import { categoryMarkerIcon } from '../mapMarkerIcons.js'

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
  prison: 'Cezaevi',
  landfill: 'Çöp Sahası',
  cemetery: 'Mezarlık',
  other: 'Diğer',
}

// Every POI category that isn't bus_stop/school/hospital (those get their
// own dedicated groups below, and their own quick-toggle chips in
// TopSearchBar) - each gets its own layer group + FilterDrawer checkbox,
// keyed by CATEGORY_LAYER_KEYS instead of one shared "diğer noktalar"
// catch-all.
const OTHER_POI_CATEGORIES = [
  'metro_station', 'train_station', 'highway_junction', 'university',
  'shopping_center', 'city_center', 'prison', 'landfill', 'cemetery',
]

// POI category -> the App.jsx `layers` state key that toggles its visibility.
export const CATEGORY_LAYER_KEYS = {
  metro_station: 'metroStations',
  train_station: 'trainStations',
  highway_junction: 'highwayJunctions',
  university: 'universities',
  shopping_center: 'shoppingCenters',
  city_center: 'cityCenters',
  prison: 'prisons',
  landfill: 'landfills',
  cemetery: 'cemeteries',
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
  return L.marker([poi.latitude, poi.longitude], {
    icon: categoryMarkerIcon(poi.category, { generic: isGeneric }),
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
  minScore = 0,
  center,
  highlightedBoundary,
  roadFeatures = [],
  highlightedRoad,
  highlightedPoi,
  layers,
  placementMode = false,
  onMapClick,
  analysisPoint,
}) {
  const mapContainerRef = useRef(null)
  const mapRef = useRef(null)
  const heatLayerRef = useRef(null)
  const markersLayerRef = useRef(null)
  const busStopLayerRef = useRef(null)
  const schoolLayerRef = useRef(null)
  const hospitalLayerRef = useRef(null)
  // category -> L.layerGroup(), one per OTHER_POI_CATEGORIES entry - built
  // once in the init effect below.
  const otherPoiGroupsRef = useRef(new Map())
  const boundaryLayerRef = useRef(null)
  const roadLinesLayerRef = useRef(null)
  const railwayLinesLayerRef = useRef(null)
  const highlightedRoadLayerRef = useRef(null)
  const highlightedPoiLayerRef = useRef(null)
  const analysisPinLayerRef = useRef(null)

  useEffect(() => {
    if (mapRef.current) return
    // Zoom 12 crops tightly to the urban core, where every region already
    // scores in the province's top ~10% - the color scale (calibrated to
    // the whole province) reads as uniformly "hot" there no matter how
    // it's tuned, hiding the real cold-to-hot gradient that's actually
    // visible a bit further out. Starting more zoomed out shows that
    // gradient immediately instead of requiring the user to zoom out first.
    // Leaflet's default zoom control sits top-left, which now collides
    // with our own hamburger/search/chip row there - move it out of the
    // way to bottom-left (Google Maps puts its map-type switcher there;
    // we don't have one, so it's free).
    const map = L.map(mapContainerRef.current, { zoomControl: false }).setView(center, 10)
    L.control.zoom({ position: 'bottomleft' }).addTo(map)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap katkıda bulunanlar',
    }).addTo(map)
    markersLayerRef.current = L.layerGroup()
    busStopLayerRef.current = L.markerClusterGroup({ maxClusterRadius: 50 })
    schoolLayerRef.current = L.markerClusterGroup({ maxClusterRadius: 50 })
    hospitalLayerRef.current = L.layerGroup()
    OTHER_POI_CATEGORIES.forEach((category) => {
      otherPoiGroupsRef.current.set(category, L.layerGroup())
    })
    boundaryLayerRef.current = L.layerGroup().addTo(map)
    roadLinesLayerRef.current = L.layerGroup()
    railwayLinesLayerRef.current = L.layerGroup()
    highlightedRoadLayerRef.current = L.layerGroup().addTo(map)
    highlightedPoiLayerRef.current = L.layerGroup().addTo(map)
    analysisPinLayerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // "Analiz Et" placement mode: crosshair cursor + next map click reports
  // its lat/lon back to the caller (App.jsx), which drops the pin and
  // opens the advisory chat panel - see analysisPoint below for the pin
  // itself.
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    const container = map.getContainer()
    container.style.cursor = placementMode ? 'crosshair' : ''
    if (!placementMode) return

    const handleClick = (event) => {
      onMapClick?.(event.latlng.lat, event.latlng.lng)
    }
    map.on('click', handleClick)
    return () => map.off('click', handleClick)
  }, [placementMode, onMapClick])

  // Analysis pin: the point currently being discussed in the advisory chat
  useEffect(() => {
    const map = mapRef.current
    const layerGroup = analysisPinLayerRef.current
    if (!map || !layerGroup) return
    layerGroup.clearLayers()
    if (!analysisPoint) return

    L.circleMarker([analysisPoint.lat, analysisPoint.lon], {
      radius: 9,
      color: '#7c3aed',
      fillColor: '#a78bfa',
      fillOpacity: 0.9,
      weight: 3,
    }).addTo(layerGroup)
  }, [analysisPoint])

  // Heatmap: data + visibility
  useEffect(() => {
    const map = mapRef.current
    if (!map) return
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current)
      heatLayerRef.current = null
    }
    if (layers.heatmap && heatmapPoints && heatmapPoints.length > 0) {
      const raster = buildHeatmapRaster(heatmapPoints, minScore)
      if (raster) {
        heatLayerRef.current = L.imageOverlay(raster.dataUrl, raster.bounds, {
          opacity: 0.8,
          interactive: false,
        }).addTo(map)
      }
    }
  }, [heatmapPoints, layers.heatmap, minScore])

  // Projects: populate markers (highways/railways render as lines instead -
  // see the road/railway line effects below - so they're excluded here)
  useEffect(() => {
    const layerGroup = markersLayerRef.current
    if (!layerGroup) return
    layerGroup.clearLayers()
    projects
      .filter((project) => project.project_type !== 'highway' && project.project_type !== 'railway')
      .forEach((project) => {
        L.marker([project.latitude, project.longitude], {
          icon: categoryMarkerIcon(project.project_type),
        })
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

  // Road/railway lines: populate (real OSM line geometry - see
  // backend/app/domain/entities/road_geometry.py - independent of the
  // single-point Project rows used for scoring, which are unaffected)
  useEffect(() => {
    const roadGroup = roadLinesLayerRef.current
    const railwayGroup = railwayLinesLayerRef.current
    if (!roadGroup || !railwayGroup) return
    roadGroup.clearLayers()
    railwayGroup.clearLayers()

    const bindPopup = (layer, feature) => {
      layer
        .bindTooltip(feature.properties.name, { sticky: true })
        .bindPopup(
          `<strong>${feature.properties.name}</strong><br/>${
            PROJECT_TYPE_LABELS[feature.properties.project_type] || feature.properties.project_type
          }`,
        )
    }

    L.geoJSON(
      { type: 'FeatureCollection', features: roadFeatures.filter((f) => f.properties.project_type === 'highway') },
      { style: { color: '#2563eb', weight: 3 }, onEachFeature: (feature, layer) => bindPopup(layer, feature) },
    ).addTo(roadGroup)

    L.geoJSON(
      { type: 'FeatureCollection', features: roadFeatures.filter((f) => f.properties.project_type === 'railway') },
      {
        style: { color: '#6b7280', weight: 2, dashArray: '6 4' },
        onEachFeature: (feature, layer) => bindPopup(layer, feature),
      },
    ).addTo(railwayGroup)
  }, [roadFeatures])

  // Road lines: visibility
  useEffect(() => {
    const map = mapRef.current
    const layerGroup = roadLinesLayerRef.current
    if (!map || !layerGroup) return
    if (layers.roads) {
      map.addLayer(layerGroup)
    } else {
      map.removeLayer(layerGroup)
    }
  }, [layers.roads])

  // Railway lines: visibility
  useEffect(() => {
    const map = mapRef.current
    const layerGroup = railwayLinesLayerRef.current
    if (!map || !layerGroup) return
    if (layers.railways) {
      map.addLayer(layerGroup)
    } else {
      map.removeLayer(layerGroup)
    }
  }, [layers.railways])

  // Highlighted road/railway (from the search panel)
  useEffect(() => {
    const map = mapRef.current
    const layerGroup = highlightedRoadLayerRef.current
    if (!map || !layerGroup) return
    layerGroup.clearLayers()
    if (!highlightedRoad) return

    const geoJsonLayer = L.geoJSON(highlightedRoad, { style: { color: '#facc15', weight: 5 } })
    geoJsonLayer.addTo(layerGroup)
    const bounds = geoJsonLayer.getBounds()
    if (bounds.isValid()) {
      map.fitBounds(bounds, { padding: [40, 40] })
    }
  }, [highlightedRoad])

  // Highlighted POI (from the top search bar - a school/hospital result,
  // rendered directly here rather than relying on the lazy-loaded POI
  // marker layers, which may not even be fetched yet at search time)
  useEffect(() => {
    const map = mapRef.current
    const layerGroup = highlightedPoiLayerRef.current
    if (!map || !layerGroup) return
    layerGroup.clearLayers()
    if (!highlightedPoi) return

    L.circleMarker([highlightedPoi.latitude, highlightedPoi.longitude], {
      radius: 10,
      color: '#facc15',
      fillColor: '#fde047',
      fillOpacity: 0.9,
      weight: 3,
    })
      .bindPopup(`<strong>${highlightedPoi.name}</strong>`)
      .addTo(layerGroup)
      .openPopup()
    map.setView([highlightedPoi.latitude, highlightedPoi.longitude], 15)
  }, [highlightedPoi])

  // POIs: split into bus stops / schools / hospitals / one group per other
  // category (OTHER_POI_CATEGORIES), populate each group
  useEffect(() => {
    const busStopGroup = busStopLayerRef.current
    const schoolGroup = schoolLayerRef.current
    const hospitalGroup = hospitalLayerRef.current
    const otherGroups = otherPoiGroupsRef.current
    if (!busStopGroup || !schoolGroup || !hospitalGroup || otherGroups.size === 0) return
    busStopGroup.clearLayers()
    schoolGroup.clearLayers()
    hospitalGroup.clearLayers()
    otherGroups.forEach((group) => group.clearLayers())
    pointsOfInterest.forEach((poi) => {
      const marker = poiCircleMarker(poi)
      if (poi.category === 'bus_stop') {
        busStopGroup.addLayer(marker)
      } else if (poi.category === 'school') {
        schoolGroup.addLayer(marker)
      } else if (poi.category === 'hospital') {
        hospitalGroup.addLayer(marker)
      } else {
        otherGroups.get(poi.category)?.addLayer(marker)
      }
    })
  }, [pointsOfInterest])

  // POIs: visibility (bus stops, schools, hospitals, and other POIs toggle independently)
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
    const hospitalGroup = hospitalLayerRef.current
    if (!map || !hospitalGroup) return
    if (layers.hospitals) {
      map.addLayer(hospitalGroup)
    } else {
      map.removeLayer(hospitalGroup)
    }
  }, [layers.hospitals])

  // Other POI categories: each toggles independently via its own
  // FilterDrawer checkbox (see CATEGORY_LAYER_KEYS) instead of one shared
  // "diğer noktalar" catch-all.
  useEffect(() => {
    const map = mapRef.current
    const otherGroups = otherPoiGroupsRef.current
    if (!map || otherGroups.size === 0) return
    OTHER_POI_CATEGORIES.forEach((category) => {
      const group = otherGroups.get(category)
      if (layers[CATEGORY_LAYER_KEYS[category]]) {
        map.addLayer(group)
      } else {
        map.removeLayer(group)
      }
    })
  }, [layers])

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
