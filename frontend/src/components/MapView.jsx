import L from 'leaflet'
import 'leaflet.heat'
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
  bus_stop: 'Otobüs Durağı/Terminali',
  hospital: 'Hastane',
  shopping_center: 'Çarşı / AVM',
  school: 'Okul',
  city_center: 'Şehir Merkezi',
  other: 'Diğer',
}

export default function MapView({ projects, pointsOfInterest = [], heatmapPoints, center }) {
  const mapContainerRef = useRef(null)
  const mapRef = useRef(null)
  const heatLayerRef = useRef(null)
  const markersLayerRef = useRef(null)
  const poiLayerRef = useRef(null)

  useEffect(() => {
    if (mapRef.current) return
    const map = L.map(mapContainerRef.current).setView(center, 12)
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; OpenStreetMap katkıda bulunanlar',
    }).addTo(map)
    markersLayerRef.current = L.layerGroup().addTo(map)
    poiLayerRef.current = L.layerGroup().addTo(map)
    mapRef.current = map

    return () => {
      map.remove()
      mapRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const map = mapRef.current
    if (!map) return

    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current)
      heatLayerRef.current = null
    }
    if (heatmapPoints && heatmapPoints.length > 0) {
      const heatData = heatmapPoints.map((p) => [p.center_lat, p.center_lon, p.score])
      heatLayerRef.current = L.heatLayer(heatData, { radius: 35, blur: 25, maxZoom: 14 }).addTo(map)
    }
  }, [heatmapPoints])

  useEffect(() => {
    const layerGroup = markersLayerRef.current
    if (!layerGroup) return
    layerGroup.clearLayers()
    projects.forEach((project) => {
      L.marker([project.latitude, project.longitude])
        .bindPopup(
          `<strong>${project.name}</strong><br/>${
            PROJECT_TYPE_LABELS[project.project_type] || project.project_type
          }<br/>${project.status}`,
        )
        .addTo(layerGroup)
    })
  }, [projects])

  useEffect(() => {
    const layerGroup = poiLayerRef.current
    if (!layerGroup) return
    layerGroup.clearLayers()
    pointsOfInterest.forEach((poi) => {
      L.circleMarker([poi.latitude, poi.longitude], {
        radius: 7,
        color: '#0f766e',
        fillColor: '#14b8a6',
        fillOpacity: 0.9,
        weight: 2,
      })
        .bindPopup(
          `<strong>${poi.name}</strong><br/>${POI_CATEGORY_LABELS[poi.category] || poi.category}`,
        )
        .addTo(layerGroup)
    })
  }, [pointsOfInterest])

  return <div ref={mapContainerRef} style={{ height: '100vh', width: '100%' }} />
}
