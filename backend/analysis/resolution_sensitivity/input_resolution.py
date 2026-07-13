"""Module 6a: input data resolution ceiling.

A grid finer than an input layer's own native resolution doesn't add real
detail - it just interpolates/replicates the same coarse value across many
small cells, which looks more precise than it is (a textbook MAUP
artifact). This module measures the actual resolution ceiling of every
input this project's scoring model really uses, and flags any requested
grid resolution that falls below it - honestly, per real ingested data,
not invented placeholder layers.
"""

from dataclasses import dataclass
from typing import List

import geopandas as gpd
import numpy as np
from geoalchemy2.shape import to_shape
from sqlalchemy.orm import Session

from app.infrastructure.persistence.models import DistrictBoundaryModel
from analysis.resolution_sensitivity import config


@dataclass
class InputResolutionCeiling:
    layer_name: str
    ceiling_description: str
    effective_linear_resolution_m: float | None  # None if not applicable (point-vector layers)


def measure_mahalle_polygon_resolution(session: Session) -> InputResolutionCeiling:
    """Population growth rate, growth momentum, and growth-direction
    sectors (see the scoring model's contributors 12-14 in the project's
    data-sourcing report) are all attached to a region via point-in-
    mahalle-polygon lookup - see
    infrastructure/persistence/repositories/district_boundary_repository.py.
    Every point inside the same mahalle gets the identical value, no
    matter how finely the grid is cut. This computes the real effective
    linear resolution of that polygon layer (sqrt of mean area) from the
    677 actually-ingested mahalle boundaries, not an assumption.
    """
    rows = (
        session.query(DistrictBoundaryModel.boundary)
        .filter(DistrictBoundaryModel.city == config.CITY)
        .all()
    )
    if not rows:
        return InputResolutionCeiling("Mahalle (nüfus/büyüme) poligonları", "Veri bulunamadı", None)

    polygons_wgs84 = gpd.GeoSeries([to_shape(row[0]) for row in rows], crs=config.CRS_GEOGRAPHIC)
    polygons_metric = polygons_wgs84.to_crs(config.CRS_METRIC)
    areas_m2 = polygons_metric.area.values

    mean_area = float(np.mean(areas_m2))
    median_area = float(np.median(areas_m2))
    effective_resolution = float(np.sqrt(mean_area))

    description = (
        f"{len(rows)} mahalle poligonu; ortalama alan {mean_area / 1e6:.2f} km^2 "
        f"(medyan {median_area / 1e6:.2f} km^2) -> etkin dogrusal cozunurluk "
        f"~{effective_resolution:.0f} m (alanin karekoku)"
    )
    return InputResolutionCeiling("Mahalle (nüfus/büyüme) poligonları", description, effective_resolution)


def point_and_vector_layer_notes() -> List[InputResolutionCeiling]:
    """OSM-sourced point/line features (stations, junctions, universities,
    highways, hazard/LULU points) have no fixed grid resolution - they're
    exact coordinates, not a raster or polygon tessellation. There's still
    a "meaningful variation scale" though: the distance-band functions
    that turn "distance to nearest X" into a score (see the individual
    contributor modules) only change appreciably over the widths of their
    own bands - refining the grid far below a band's narrowest segment
    doesn't reveal new real structure, it just samples the same smooth
    curve more densely. Ranges below are the real constants from each
    contributor's source, not estimates.
    """
    return [
        InputResolutionCeiling(
            "Otoyol kavşağı erişimi (nokta)",
            "Bant genişliği ~150 m (kavşak dibi cezası) - 8 km (etkinin bittiği nokta); en dar segment ~150-850 m",
            None,
        ),
        InputResolutionCeiling(
            "Tren istasyonu erişimi (nokta)",
            "Bant genişliği ~50 m - 3 km; en dar segment (tepe noktası öncesi) ~50-400 m",
            None,
        ),
        InputResolutionCeiling(
            "Otoyol/demiryolu gürültüsü (hat)",
            "Bant genişliği 0-200 m - bu faktör 200m'nin altında zaten tam çözünürlükte",
            None,
        ),
        InputResolutionCeiling(
            "Şehir merkezi (CBD) erişimi (nokta)",
            "Bant genişliği 0-30 km - şehir ölçeğinde yumuşak bir eğri, en dar segment ~5 km",
            None,
        ),
        InputResolutionCeiling(
            "OSB/üniversite erişimi (nokta)",
            "Bant genişliği 0-10 km; en dar segment ~500 m - 2 km",
            None,
        ),
        InputResolutionCeiling(
            "Olumsuz komşuluk - cezaevi/çöp/mezarlık (nokta)",
            "Bant genişliği 0-3 km",
            None,
        ),
    ]


def unavailable_layers_note() -> List[InputResolutionCeiling]:
    """Explicitly documenting what this project does NOT have, rather than
    fabricating placeholder resolution numbers for layers that were never
    ingested - see the data-sourcing report sections 1.8/1.9/5.1 for why.
    """
    return [
        InputResolutionCeiling("Sayısal Yükseklik Modeli (DEM) / eğim", "PROJEDE YOK - hiçbir kaynaktan alınmadı", None),
        InputResolutionCeiling("Zemin sınıfı / sıvılaşma mikrobölgeleme", "PROJEDE YOK - AFAD/MTA erişilebilir bulunamadı", None),
        InputResolutionCeiling("İmar durumu / arazi kullanım planı", "PROJEDE YOK - hiçbir kaynaktan alınmadı", None),
        InputResolutionCeiling("Arsa/emlak rayiç veya işlem fiyatı", "PROJEDE YOK - erişilebilir kaynak bulunamadı", None),
    ]


def resolution_warnings(mahalle_ceiling_m: float, requested_resolutions_m: List[float]) -> List[str]:
    warnings = []
    for res in requested_resolutions_m:
        if res < mahalle_ceiling_m:
            warnings.append(
                f"UYARI: {res:.0f} m çözünürlük, mahalle poligon verisinin gerçek çözünürlüğünün "
                f"(~{mahalle_ceiling_m:.0f} m) altında - nüfus artışı/momentum/büyüme yönü "
                f"faktörleri bu ölçekte SAHTE DETAY üretir (aynı mahalle içindeki tüm hücreler "
                f"zaten birebir aynı değeri taşıyor, sadece daha küçük parçalara bölünmüş görünüyor)."
            )
    return warnings
