import { useEffect, useState } from 'react'
import {
  fetchDistrictBoundary,
  fetchDistricts,
  fetchHeatmap,
  fetchPointsOfInterest,
  fetchProjects,
  fetchRoadGeometries,
} from './api/client.js'
import AdvisoryChatPanel from './components/AdvisoryChatPanel.jsx'
import DistrictDetailPanel from './components/DistrictDetailPanel.jsx'
import FilterDrawer from './components/FilterDrawer.jsx'
import { ChatIcon, PinIcon } from './components/icons.jsx'
import MapView from './components/MapView.jsx'
import TopSearchBar from './components/TopSearchBar.jsx'

const CITY = 'sakarya'
const SAKARYA_CENTER = [40.7569, 30.3781]

const INITIAL_LAYERS = {
  heatmap: true,
  projects: true,
  roads: true,
  railways: true,
  // Bus stops (2600+), schools (683), and hospitals are only fetched once
  // switched on - loading them eagerly on every page visit was the
  // reported perf issue. Schools/hospitals are separately available for
  // search via searchablePois below (a small, always-eager dataset), which
  // is independent of whether their map markers are actually rendered yet.
  busStops: false,
  schools: false,
  hospitals: false,
  otherPois: true,
}

export default function App() {
  const [projects, setProjects] = useState([])
  const [pointsOfInterest, setPointsOfInterest] = useState([])
  const [poisRequested, setPoisRequested] = useState(false)
  const [searchablePois, setSearchablePois] = useState([])
  const [heatmapPoints, setHeatmapPoints] = useState([])
  const [districts, setDistricts] = useState([])
  const [selectedDistrict, setSelectedDistrict] = useState(null)
  const [selectedDistrictBoundary, setSelectedDistrictBoundary] = useState(null)
  const [districtDetailTarget, setDistrictDetailTarget] = useState(null)
  const [roadGeometries, setRoadGeometries] = useState({ type: 'FeatureCollection', features: [] })
  const [selectedRoad, setSelectedRoad] = useState(null)
  const [highlightedPoi, setHighlightedPoi] = useState(null)
  const [layers, setLayers] = useState(INITIAL_LAYERS)
  const [landUseProfile, setLandUseProfile] = useState('balanced')
  const [minScore, setMinScore] = useState(0)
  const [menuOpen, setMenuOpen] = useState(false)
  const [placementMode, setPlacementMode] = useState(false)
  const [analysisPoint, setAnalysisPoint] = useState(null)
  // Separate from analysisPoint - closing the panel just hides it (see
  // AdvisoryChatPanel, which stays mounted and keeps its conversation
  // state), it doesn't clear the selected point/conversation. Reopened any
  // time via the chat toggle button below.
  const [chatOpen, setChatOpen] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      fetchProjects(CITY),
      fetchDistricts(CITY),
      fetchRoadGeometries(CITY),
      fetchPointsOfInterest(CITY, ['school', 'hospital']),
    ])
      .then(([projectsData, districtsData, roadGeometriesData, searchablePoisData]) => {
        setProjects(projectsData)
        setDistricts(districtsData)
        setRoadGeometries(roadGeometriesData)
        setSearchablePois(searchablePoisData)
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
    const needsPois = layers.busStops || layers.schools || layers.hospitals || layers.otherPois
    if (!needsPois || poisRequested) return
    setPoisRequested(true)
    fetchPointsOfInterest(CITY).then(setPointsOfInterest).catch((err) => setError(err.message))
  }, [layers.busStops, layers.schools, layers.hospitals, layers.otherPois, poisRequested])

  const handleToggleLayer = (key) => {
    setLayers((prev) => ({ ...prev, [key]: !prev[key] }))
  }

  const handleSelectDistrict = (district) => {
    setSelectedDistrict(district)
    fetchDistrictBoundary(CITY, district.name)
      .then(setSelectedDistrictBoundary)
      .catch((err) => setError(err.message))
  }

  const handleSelectSearchResult = (result) => {
    if (result.type === 'district') {
      handleSelectDistrict(result.data)
    } else if (result.type === 'road') {
      setSelectedRoad(result.data)
    } else {
      // school / hospital - a single point, not yet necessarily loaded as
      // a map marker (that layer may still be lazy/off) - highlight it
      // directly and make sure its layer is switched on too.
      setHighlightedPoi(result.data)
      if (!layers[`${result.type}s`]) handleToggleLayer(`${result.type}s`)
    }
  }

  const handleMapClick = (lat, lon) => {
    setAnalysisPoint({ lat, lon })
    setPlacementMode(false)
    setChatOpen(true)
  }

  return (
    <div>
      {error && <div className="error-banner">Veri yüklenemedi: {error}</div>}

      <TopSearchBar
        districts={districts}
        roadFeatures={roadGeometries.features}
        searchablePois={searchablePois}
        layers={layers}
        onToggleLayer={handleToggleLayer}
        onSelectResult={handleSelectSearchResult}
        onToggleMenu={() => setMenuOpen((open) => !open)}
      />

      <FilterDrawer
        isOpen={menuOpen}
        onClose={() => setMenuOpen(false)}
        districts={districts}
        selectedDistrict={selectedDistrict}
        onSelectDistrict={handleSelectDistrict}
        onOpenDistrictDetail={setDistrictDetailTarget}
        layers={layers}
        onToggleLayer={handleToggleLayer}
        landUseProfile={landUseProfile}
        onChangeLandUseProfile={setLandUseProfile}
        minScore={minScore}
        onChangeMinScore={setMinScore}
      />

      <DistrictDetailPanel
        city={CITY}
        district={districtDetailTarget}
        landUseProfile={landUseProfile}
        onClose={() => setDistrictDetailTarget(null)}
      />

      <button
        className={`analyze-button ${placementMode ? 'active' : ''}`}
        onClick={() => setPlacementMode((mode) => !mode)}
      >
        <PinIcon size={18} />
        {placementMode ? 'Haritada bir yere tıklayın...' : 'Analiz Et'}
      </button>

      <button className="chat-toggle-button" onClick={() => setChatOpen((open) => !open)} aria-label="Danışma sohbeti">
        <ChatIcon />
      </button>

      <AdvisoryChatPanel
        city={CITY}
        analysisPoint={analysisPoint}
        isOpen={chatOpen}
        onClose={() => setChatOpen(false)}
      />

      <MapView
        projects={projects}
        pointsOfInterest={pointsOfInterest}
        heatmapPoints={heatmapPoints}
        minScore={minScore}
        center={SAKARYA_CENTER}
        highlightedBoundary={selectedDistrictBoundary}
        roadFeatures={roadGeometries.features}
        highlightedRoad={selectedRoad}
        highlightedPoi={highlightedPoi}
        layers={layers}
        placementMode={placementMode}
        onMapClick={handleMapClick}
        analysisPoint={analysisPoint}
      />
    </div>
  )
}
