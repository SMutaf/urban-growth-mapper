// Renders the heatmap's regular scoring grid as a smoothly interpolated
// raster image instead of drawing individual point blobs. Point-based
// libraries (leaflet.heat, heatmap.js) render each grid cell as its own
// circle; when the circle radius is close in size to the grid spacing (as
// it inevitably is somewhere in the zoom range, since a fixed real-world
// radius still covers a different number of screen pixels at every zoom),
// the overlapping circles create a checkerboard/moire pattern instead of a
// smooth field. A bilinear-interpolated raster has no such artifact - it's
// a real georeferenced image, so Leaflet scales it exactly like a map
// tile, and it looks equally smooth at every zoom level.

const COLOR_SEQUENCE = [
  [33, 102, 234],
  [34, 193, 224],
  [61, 220, 132],
  [245, 230, 66],
  [245, 167, 66],
  [224, 52, 47],
]

// Real growth scores are right-skewed (most regions cluster in a low-to-mid
// range, with a longer tail of exceptional spots) even after the backend's
// log-normalization (see normalization.py) - so fixed 0/0.25/0.5/0.7/0.85/1
// gradient stops still spend half the color range on values below the
// median and barely reach yellow/orange/red anywhere. Deriving the stops
// from the *actual* dataset's quantiles each time (a standard quantile-
// stretch/histogram-equalization technique) fixes that - the median region
// always lands on the middle color, not wherever its raw score happens to
// fall on a fixed axis.
//
// This computes stop *values* (not per-region ranks) from the whole
// dataset once, then colors every pixel by where its value falls between
// those fixed value breakpoints - unlike ranking each region individually,
// a given score always maps to the same color regardless of which part of
// the map is currently in view, so panning/zooming never repaints anything.
const STOP_QUANTILES = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]

function computeColorStops(heatmapPoints) {
  const sorted = [...heatmapPoints].map((p) => p.score).sort((a, b) => a - b)
  const n = sorted.length
  return STOP_QUANTILES.map((q, i) => {
    const index = Math.min(n - 1, Math.max(0, Math.round(q * (n - 1))))
    return [sorted[index], COLOR_SEQUENCE[i]]
  })
}

function colorForScore(score, stops) {
  if (score <= stops[0][0]) return stops[0][1]
  const last = stops[stops.length - 1]
  if (score >= last[0]) return last[1]
  for (let i = 0; i < stops.length - 1; i++) {
    const [s0, c0] = stops[i]
    const [s1, c1] = stops[i + 1]
    if (score <= s1) {
      const t = s1 === s0 ? 0 : (score - s0) / (s1 - s0)
      return [
        c0[0] + t * (c1[0] - c0[0]),
        c0[1] + t * (c1[1] - c0[1]),
        c0[2] + t * (c1[2] - c0[2]),
      ]
    }
  }
  return last[1]
}

// Where `score` falls along the stop sequence, as a 0-1 fraction - used for
// opacity so faint/uncertain-looking low values and solid high values track
// the same quantile-stretched scale as the color itself, instead of
// opacity separately clustering low under a plain linear score mapping.
function stopPosition(score, stops) {
  const n = stops.length
  if (score <= stops[0][0]) return 0
  if (score >= stops[n - 1][0]) return 1
  for (let i = 0; i < n - 1; i++) {
    const [s0] = stops[i]
    const [s1] = stops[i + 1]
    if (score <= s1) {
      const t = s1 === s0 ? 0 : (score - s0) / (s1 - s0)
      return (i + t) / (n - 1)
    }
  }
  return 1
}

function buildGrid(heatmapPoints) {
  const lats = [...new Set(heatmapPoints.map((p) => p.center_lat))].sort((a, b) => a - b)
  const lons = [...new Set(heatmapPoints.map((p) => p.center_lon))].sort((a, b) => a - b)
  if (lats.length < 2 || lons.length < 2) return null

  const latIndex = new Map(lats.map((lat, i) => [lat, i]))
  const lonIndex = new Map(lons.map((lon, i) => [lon, i]))
  const grid = Array.from({ length: lats.length }, () => new Array(lons.length).fill(null))
  heatmapPoints.forEach((p) => {
    const row = latIndex.get(p.center_lat)
    const col = lonIndex.get(p.center_lon)
    if (row !== undefined && col !== undefined) grid[row][col] = p.score
  })
  return { grid, lats, lons }
}

// A null cell can mean two different things: a genuine gap surrounded by
// real data (e.g. a region that failed to score - rare), or a cell outside
// the city's real (polygon-clipped) boundary entirely, which is the common
// case once the grid covers an irregularly shaped area like a whole
// province rather than a roughly-rectangular urban core. Only the first
// kind should be filled in - a null cell with real data on (almost) every
// side is very likely a genuine hole; a null cell at the edge of the data
// footprint (1-2 real neighbours) is very likely actually outside the
// boundary and should stay null so it renders transparent, not extrapolated
// color bleeding into a neighbouring province or the sea.
function fillIsolatedGaps(grid, nRows, nCols) {
  const filled = grid.map((row) => [...row])
  for (let r = 0; r < nRows; r++) {
    for (let c = 0; c < nCols; c++) {
      if (grid[r][c] !== null) continue
      const neighbours = []
      for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
        const nr = r + dr
        const nc = c + dc
        if (nr >= 0 && nr < nRows && nc >= 0 && nc < nCols && grid[nr][nc] !== null) {
          neighbours.push(grid[nr][nc])
        }
      }
      if (neighbours.length >= 3) {
        filled[r][c] = neighbours.reduce((a, b) => a + b, 0) / neighbours.length
      }
    }
  }
  return filled
}

// Returns null (meaning "outside real coverage, render transparent") if any
// of the four surrounding grid cells has no data.
function bilinearSample(grid, nRows, nCols, rowF, colF) {
  const r0 = Math.max(0, Math.min(nRows - 1, Math.floor(rowF)))
  const r1 = Math.min(nRows - 1, r0 + 1)
  const c0 = Math.max(0, Math.min(nCols - 1, Math.floor(colF)))
  const c1 = Math.min(nCols - 1, c0 + 1)
  const v00 = grid[r0][c0]
  const v01 = grid[r0][c1]
  const v10 = grid[r1][c0]
  const v11 = grid[r1][c1]
  if (v00 === null || v01 === null || v10 === null || v11 === null) return null
  const tr = rowF - r0
  const tc = colF - c0
  const top = v00 + (v01 - v00) * tc
  const bottom = v10 + (v11 - v10) * tc
  return top + (bottom - top) * tr
}

const SUPERSAMPLE = 5
const MIN_ALPHA = 40
const MAX_ALPHA = 235

export function buildHeatmapRaster(heatmapPoints) {
  if (!heatmapPoints || heatmapPoints.length === 0) return null
  const colorStops = computeColorStops(heatmapPoints)
  const built = buildGrid(heatmapPoints)
  if (!built) return null
  const { lats, lons } = built
  const nRows = lats.length
  const nCols = lons.length
  const grid = fillIsolatedGaps(built.grid, nRows, nCols)

  const outW = nCols * SUPERSAMPLE
  const outH = nRows * SUPERSAMPLE
  const canvas = document.createElement('canvas')
  canvas.width = outW
  canvas.height = outH
  const ctx = canvas.getContext('2d')
  const imageData = ctx.createImageData(outW, outH)

  for (let y = 0; y < outH; y++) {
    // lats[] is sorted south-to-north (ascending), but image row 0 is the
    // top of the overlay (north) - flip vertically.
    const rowF = ((outH - 1 - y) / (outH - 1)) * (nRows - 1)
    for (let x = 0; x < outW; x++) {
      const colF = (x / (outW - 1)) * (nCols - 1)
      const score = bilinearSample(grid, nRows, nCols, rowF, colF)
      const idx = (y * outW + x) * 4
      if (score === null) {
        imageData.data[idx + 3] = 0
        continue
      }
      const [r, g, b] = colorForScore(score, colorStops)
      const alpha = MIN_ALPHA + stopPosition(score, colorStops) * (MAX_ALPHA - MIN_ALPHA)
      imageData.data[idx] = r
      imageData.data[idx + 1] = g
      imageData.data[idx + 2] = b
      imageData.data[idx + 3] = alpha
    }
  }
  ctx.putImageData(imageData, 0, 0)

  const halfLatStep = (lats[1] - lats[0]) / 2
  const halfLonStep = (lons[1] - lons[0]) / 2
  const bounds = [
    [lats[0] - halfLatStep, lons[0] - halfLonStep],
    [lats[nRows - 1] + halfLatStep, lons[nCols - 1] + halfLonStep],
  ]
  return { dataUrl: canvas.toDataURL(), bounds }
}
