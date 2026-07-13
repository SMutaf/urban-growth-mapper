import { useEffect, useState } from 'react'
import {
  fetchDistrictBoundary,
  fetchDistricts,
  fetchHeatmap,
  fetchPointsOfInterest,
  fetchProjects,
  fetchRoadGeometries,
} from './api/client.js'
import DistrictPanel from './components/DistrictPanel.jsx'
import LayerControlPanel from './components/LayerControlPanel.jsx'
import MapView from './components/MapView.jsx'
import RoadSearchPanel from './components/RoadSearchPanel.jsx'

const CITY = 'sakarya'
const SAKARYA_CENTER = [40.7569, 30.3781]

const INITIAL_LAYERS = {
  heatmap: true,
  projects: true,
  roads: true,
  railways: true,
  // Bus stops (2600+) and schools (683) are only fetched once switched on -
  // loading them eagerly on every page visit was the reported perf issue.
  busStops: false,
  schools: false,
  otherPois: true,
}

export default function App() {
  const [projects, setProjects] = useState([])
  const [pointsOfInterest, setPointsOfInterest] = useState([])
  const [poisRequested, setPoisRequested] = useState(false)
  const [heatmapPoints, setHeatmapPoints] = useState([])
  const [districts, setDistricts] = useState([])
  const [selectedDistrict, setSelectedDistrict] = useState(null)
  const [selectedDistrictBoundary, setSelectedDistrictBoundary] = useState(null)
  const [roadGeometries, setRoadGeometries] = useState({ type: 'FeatureCollection', features: [] })
  const [selectedRoad, setSelectedRoad] = useState(null)
  const [layers, setLayers] = useState(INITIAL_LAYERS)
  const [landUseProfile, setLandUseProfile] = useState('balanced')
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([fetchProjects(CITY), fetchDistricts(CITY), fetchRoadGeometries(CITY)])
      .then(([projectsData, districtsData, roadGeometriesData]) => {
        setProjects(projectsData)
        setDistricts(districtsData)
        setRoadGeometries(roadGeometriesData)
      })
      .catch((err) => setError(err.message))
  }, [])

  useEffect(() => {
    // Fetched separately - the fine-grained heatmap grid takes a few
    // seconds to score server-side, and shouldn't hold up the rest of the
    // page (map, projects, district panel) from rendering. Re-fetched
    // whenever the land-use profile changes (residential/commercial/
    // industrial reweight the same underlying factors differently).
    fetchHeatmap(CITY, landUseProfile)
      .then((heatmapData) => setHeatmapPoints(heatmapData.points))
      .catch((err) => setError(err.message))
  }, [landUseProfile])

  useEffect(() => {
    const needsPois = layers.busStops || layers.schools || layers.otherPois
    if (!needsPois || poisRequested) return
    setPoisRequested(true)
    fetchPointsOfInterest(CITY).then(setPointsOfInterest).catch((err) => setError(err.message))
  }, [layers.busStops, layers.schools, layers.otherPois, poisRequested])

  const handleToggleLayer = (key) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSelectDistrict = (district) => {
    setSelectedDistrict(district)
    fetchDistrictBoundary(CITY, district.name)
      .then(setSelectedDistrictBoundary)
      .catch((err) => setError(err.message))
  }

  const handleSelectRoad = (feature) => {
    // roadGeometries is already the full FeatureCollection fetched once
    // above - no per-name fetch needed here, unlike district boundaries.
    setSelectedRoad(feature)
  }

  return (
    <div>
      {error && <div className="error-banner">Veri yüklenemedi: {error}</div>}
      <DistrictPanel
        districts={districts}
        selectedDistrict={selectedDistrict}
        onSelectDistrict={handleSelectDistrict}
      />
      <LayerControlPanel
        layers={layers}
        onToggleLayer={handleToggleLayer}
        landUseProfile={landUseProfile}
        onChangeLandUseProfile={setLandUseProfile}
      />
      <RoadSearchPanel
        roadFeatures={roadGeometries.features}
        selectedRoadName={selectedRoad?.properties?.name}
        onSelectRoad={handleSelectRoad}
      />
      <MapView
        projects={projects}
        pointsOfInterest={pointsOfInterest}
        heatmapPoints={heatmapPoints}
        center={SAKARYA_CENTER}
        highlightedBoundary={selectedDistrictBoundary}
        roadFeatures={roadGeometries.features}
        highlightedRoad={selectedRoad}
        layers={layers}
      />
    </div>
  )
}
