const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

async function request(path) {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

// Advisory endpoints return a specific, already-Turkish error message in
// {detail: "..."} (e.g. "Ollama sunucusuna ulaşılamadı") on failure - see
// backend/app/api/v1/endpoints/advisory.py. Surfacing that instead of a
// generic "API request failed" is the whole point of the backend raising
// AdvisoryError with a clear message rather than returning empty.
async function postJson(path, body) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    throw new Error(data?.detail || `API request failed: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export function fetchProjects(city) {
  return request(`/projects?city=${encodeURIComponent(city)}`)
}

export function fetchHeatmap(city, profile = 'balanced') {
  return request(`/heatmap?city=${encodeURIComponent(city)}&profile=${encodeURIComponent(profile)}`)
}

export function fetchPointsOfInterest(city, categories = []) {
  const categoryParams = categories.map((c) => `category=${encodeURIComponent(c)}`).join('&')
  return request(
    `/points-of-interest?city=${encodeURIComponent(city)}${categoryParams ? `&${categoryParams}` : ''}`,
  )
}

export function fetchDistricts(city) {
  return request(`/districts?city=${encodeURIComponent(city)}`)
}

export function fetchDistrictBoundary(city, districtName) {
  return request(
    `/districts/${encodeURIComponent(districtName)}/boundary?city=${encodeURIComponent(city)}`,
  )
}

export function fetchRoadGeometries(city) {
  return request(`/road-geometries?city=${encodeURIComponent(city)}`)
}

export function fetchMahalleScores(city, districtName, profile = 'balanced') {
  return request(
    `/districts/${encodeURIComponent(districtName)}/mahalle-scores?city=${encodeURIComponent(city)}&profile=${encodeURIComponent(profile)}`,
  )
}

export function startAdvisory(city, lat, lon, message) {
  return postJson('/advisory', { city, lat, lon, message })
}

export function continueAdvisory(context, conversation) {
  return postJson('/advisory/chat', { context, conversation })
}
