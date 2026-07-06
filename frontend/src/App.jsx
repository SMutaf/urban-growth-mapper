import { useEffect, useState } from 'react'
import { fetchHeatmap, fetchPointsOfInterest, fetchProjects } from './api/client.js'
import MapView from './components/MapView.jsx'

const CITY = 'sakarya'
const SAKARYA_CENTER = [40.7569, 30.3781]

export default function App() {
  const [projects, setProjects] = useState([])
  const [pointsOfInterest, setPointsOfInterest] = useState([])
  const [heatmapPoints, setHeatmapPoints] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([fetchProjects(CITY), fetchPointsOfInterest(CITY), fetchHeatmap(CITY)])
      .then(([projectsData, poisData, heatmapData]) => {
        setProjects(projectsData)
        setPointsOfInterest(poisData)
        setHeatmapPoints(heatmapData.points)
      })
      .catch((err) => setError(err.message))
  }, [])

  return (
    <div>
      {error && <div className="error-banner">Veri yüklenemedi: {error}</div>}
      <MapView
        projects={projects}
        pointsOfInterest={pointsOfInterest}
        heatmapPoints={heatmapPoints}
        center={SAKARYA_CENTER}
      />
    </div>
  )
}
