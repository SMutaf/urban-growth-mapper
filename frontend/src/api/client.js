const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

async function request(path) {
  const response = await fetch(`${API_BASE_URL}${path}`)
  if (!response.ok) {
    throw new Error(`API request failed: ${response.status} ${response.statusText}`)
  }
  return response.json()
}

export function fetchProjects(city) {
  return request(`/projects?city=${encodeURIComponent(city)}`)
}

export function fetchHeatmap(city) {
  return request(`/heatmap?city=${encodeURIComponent(city)}`)
}

export function fetchPointsOfInterest(city) {
  return request(`/points-of-interest?city=${encodeURIComponent(city)}`)
}

export function fetchDistricts(city) {
  return request(`/districts?city=${encodeURIComponent(city)}`)
}

export function fetchDistrictBoundary(city, districtName) {
  return request(
    `/districts/${encodeURIComponent(districtName)}/boundary?city=${encodeURIComponent(city)}`,
  )
}
