import { useEffect, useState } from 'react'
import {
  fetchDistrictBoundary,
  fetchDistricts,
  fetchHeatmap,
  fetchPointsOfInterest,
  fetchProjects,
} from './api/client.js'
import DistrictPanel from './components/DistrictPanel.jsx'
import LayerControlPanel from './components/LayerControlPanel.jsx'
import MapView from './components/MapView.jsx'

const CITY = 'sakarya'
const SAKARYA_CENTER = [40.7569, 30.3781]

const INITIAL_LAYERS = {
  heatmap: true,
  projects: true,
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
  const [layers, setLayers] = useState(INITIAL_LAYERS)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([fetchProjects(CITY), fetchHeatmap(CITY), fetchDistricts(CITY)])
      .then(([projectsData, heatmapData, districtsData]) => {
        setProjects(projectsData)
        setHeatmapPoints(heatmapData.points)
        setDistricts(districtsData)
      })
      .catch((err) => setError(err.message))
  }, [])

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

  return (
    <div>
      {error && <div className="error-banner">Veri yüklenemedi: {error}</div>}
      <DistrictPanel
        districts={districts}
        selectedDistrict={selectedDistrict}
        onSelectDistrict={handleSelectDistrict}
      />
      <LayerControlPanel layers={layers} onToggleLayer={handleToggleLayer} />
      <MapView
        projects={projects}
        pointsOfInterest={pointsOfInterest}
        heatmapPoints={heatmapPoints}
        center={SAKARYA_CENTER}
        highlightedBoundary={selectedDistrictBoundary}
        layers={layers}
      />
    </div>
  )
}
