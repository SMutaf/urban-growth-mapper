from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.project import ProjectType
from app.domain.entities.region import Region
from app.domain.geo_utils import haversine_distance_km
from app.domain.scoring.band_function import BandFunction, banded_value
from app.domain.scoring.contributors.highway_junction_access import ACCESS_BAND as _JUNCTION_BAND
from app.domain.scoring.contributors.industrial_zone_access import ACCESS_BAND as _OSB_BAND
from app.domain.scoring.contributors.university_proximity import PROXIMITY_BAND as _UNIVERSITY_BAND
from app.domain.scoring.scoring_context import ScoringContext

# Literature: real growth concentrates in the urban-rural FRINGE band - not
# the already-built core (saturated, little room left) and not remote
# countryside (disconnected, no reason to develop yet), but the
# in-between zone where moderate building density meets proximity to the
# existing urban edge (Tobler's First Law: growth propagates outward from
# what's already there, it doesn't teleport). Two independent components,
# multiplied together (neither alone is a reliable "fringe" signal - dense
# far-flung villages and vacant lots deep inside the city both fail one
# check or the other):
#
#   fringe = density_band(local building density) x edge_band(distance to
#            nearest built-up cell)
#
# LEAPFROG EXCEPTION: growth doesn't always creep outward one block at a
# time - it also jumps straight to a strong attractor (a new university
# campus, an OSB, a highway interchange) well beyond the current built
# edge, then infills around it later. If a region sits within one of
# those attractors' own established influence range (reusing
# HighwayJunctionAccessContributor / UniversityProximityContributor /
# IndustrialZoneAccessContributor's own band widths - not a new guessed
# number), only the EDGE-DISTANCE component is neutralized (forced to
# 1.0); the density component still applies normally. The attractor's own
# positive pull is already counted by its own contributor - giving fringe
# a positive edge-distance bonus too on top of that would double-count the
# same location's appeal twice. TOKİ/planned-development zone data would
# belong in this same buffer list but doesn't exist in this project (no
# ingested source - see the project's data-sourcing report) and is
# deliberately left out rather than guessed at.
#
# KNOWN LIMITATION (by design, not a bug): this factor can only pull a
# saturated urban CORE down (<1.0 - "already built out, little fringe
# potential left"). It has no way to reward vertical redevelopment/infill
# density increases in the core, since that's a genuinely different growth
# mechanism (intensification) from what this factor models (outward
# expansion) - out of scope here on purpose.

# Tight multiplier range (0.85-1.20), well inside every other contributor's
# range (0.7-1.4 - see the other contributor modules), because this is a
# new, uncalibrated factor: in a multiplicative model, an unproven factor
# shouldn't be able to dominate the score distribution the way well-
# established, literature-heavy factors (e.g. CBD access, 0.5x-3.0x) can.
# Tune only after checking against real Sakarya conversion/permit data.
DENSITY_MIN_MULTIPLIER = 0.85
DENSITY_MAX_MULTIPLIER = 1.20

# Distance (km) from a region to the nearest already-built-up cell -
# unlike the density band (whose breakpoints are derived from Sakarya's
# real data - see fringe_density_band.py), this is a physical distance and
# so uses the same literature-informed-but-uncalibrated fixed-km-breakpoint
# convention as every other banded contributor (rail/highway/university
# access etc). Right at the edge (0-150m) is mildly negative (that parcel
# is already effectively urban, not fringe); ~300m-1.5km is the peak
# expansion-front sweet spot; beyond ~5km there's no meaningful
# connection to the existing built area.
EDGE_DISTANCE_BAND: BandFunction = [(0.0, 0.9), (0.15, 1.0), (0.5, 1.15), (1.5, 1.2), (3.0, 1.0), (5.0, 0.85)]
EDGE_SEARCH_RADIUS_KM = EDGE_DISTANCE_BAND[-1][0]

# Matches scripts/ingest_sakarya_osm.py's LAND_COVER_SEARCH_RADIUS_KM (a
# circle of this radius has the same area as the production heatmap's 1km
# grid cell, pi*r^2 = 1km^2) - land cover cells already ARE density
# readings over this radius, so "the region's own local density" is just
# whichever lattice cell it's nearest to.
DENSITY_LOOKUP_RADIUS_KM = 0.56

# A land-cover cell counts as "built up" (for edge-distance purposes) once
# it has at least this many buildings within its own aggregation radius -
# an engineering heuristic to separate "a stray farm building or two" from
# "an actual settlement edge", not a literature-derived figure. Tune freely.
BUILT_UP_THRESHOLD = 3

# Independent growth-attractor buffers for the leapfrog exception, each
# reusing that factor's OWN band width (its last breakpoint - where the
# band itself returns to neutral) rather than a separately guessed radius,
# so "is this within the attractor's influence" stays consistent with what
# that attractor's own contributor already believes about its reach.
_LEAPFROG_BUFFERS_KM = {
    POICategory.HIGHWAY_JUNCTION: _JUNCTION_BAND[-1][0],
    POICategory.UNIVERSITY: _UNIVERSITY_BAND[-1][0],
}
_LEAPFROG_PROJECT_BUFFERS_KM = {
    ProjectType.INDUSTRIAL_ZONE: _OSB_BAND[-1][0],
}


class FringeContributor:
    def contribute(self, region: Region, context: ScoringContext) -> float:
        # No land cover data ingested yet for this city (see
        # scripts/ingest_sakarya_osm.py's ingest_land_cover()) - stay
        # neutral rather than letting _edge_multiplier's "nothing built-up
        # found nearby" fallback (a real, informative signal once there IS
        # data) be misread as "confirmed disconnected from civilization"
        # when it's really just "no data exists to check yet".
        if not context.land_cover_cells:
            return 1.0

        density_multiplier = self._density_multiplier(region, context)
        if self._near_growth_attractor(region, context):
            edge_multiplier = 1.0
        else:
            edge_multiplier = self._edge_multiplier(region, context)
        return density_multiplier * edge_multiplier

    @staticmethod
    def _density_multiplier(region: Region, context: ScoringContext) -> float:
        if not context.fringe_density_band:
            return 1.0
        nearby = context.land_cover_near(region.center_lat, region.center_lon, DENSITY_LOOKUP_RADIUS_KM)
        if not nearby:
            return 1.0
        nearest = min(
            nearby,
            key=lambda c: haversine_distance_km(region.center_lat, region.center_lon, c.latitude, c.longitude),
        )
        return banded_value(nearest.building_count, context.fringe_density_band)

    @staticmethod
    def _edge_multiplier(region: Region, context: ScoringContext) -> float:
        candidates = context.land_cover_near(region.center_lat, region.center_lon, EDGE_SEARCH_RADIUS_KM)
        built_cells = [c for c in candidates if c.building_count >= BUILT_UP_THRESHOLD]
        if not built_cells:
            return EDGE_DISTANCE_BAND[-1][1]  # nothing built-up within range -> disconnected floor
        nearest_km = min(
            haversine_distance_km(region.center_lat, region.center_lon, c.latitude, c.longitude)
            for c in built_cells
        )
        return banded_value(nearest_km, EDGE_DISTANCE_BAND)

    @staticmethod
    def _near_growth_attractor(region: Region, context: ScoringContext) -> bool:
        for category, buffer_km in _LEAPFROG_BUFFERS_KM.items():
            for poi in context.pois_by_category(category):
                if haversine_distance_km(region.center_lat, region.center_lon, poi.latitude, poi.longitude) <= buffer_km:
                    return True
        for project_type, buffer_km in _LEAPFROG_PROJECT_BUFFERS_KM.items():
            for project in context.projects_by_type(project_type):
                if haversine_distance_km(region.center_lat, region.center_lon, project.latitude, project.longitude) <= buffer_km:
                    return True
        return False
