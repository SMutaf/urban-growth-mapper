"""Orchestrates the point-advisory chatbot: user picks a spot on the map
and a message, gets a reply from an LLM that only interprets numbers this
backend already computed - the LLM never calculates a distance or a score
itself (see IAdvisoryLLMClient's docstring for why that boundary matters).
"""

import json
from collections import defaultdict
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from app.application.services.heatmap_service import HeatmapService
from app.domain.entities.land_use_profile import LandUseProfile
from app.domain.entities.point_of_interest import POICategory
from app.domain.entities.project import ProjectType
from app.domain.geo_utils import haversine_distance_km
from app.domain.interpretation.advisory_interfaces import IAdvisoryLLMClient
from app.domain.scoring.contributors.fringe import FringeContributor
from app.domain.entities.region import Region
from app.domain.scoring.growth_direction_analysis import bearing_degrees
from app.domain.scoring.scoring_context import ScoringContext
from app.infrastructure.persistence.repositories.district_boundary_repository import (
    SqlAlchemyDistrictBoundaryRepository,
)

NEARBY_RADIUS_KM = 1.0
# A category with more entries than this within 1km (typically bus stops -
# a dense area can have a dozen) collapses into one summary (nearest
# distance + count) instead of listing every one by name - see
# _nearby_features.
NEARBY_AGGREGATE_THRESHOLD = 3

# Compass labels for growth_direction_analysis.compute_sector_growth's
# 8-sector output - index 0 is the sector centered on due north, clockwise,
# matching that function's own convention exactly.
COMPASS_SECTOR_LABELS_TR = [
    "kuzey", "kuzeydogu", "dogu", "guneydogu",
    "guney", "guneybati", "bati", "kuzeybati",
]

# Turkish labels for the JSON context sent to the LLM - translated here,
# backend-side, rather than leaving the LLM to guess/translate category
# codes itself (keeps with "the LLM only interprets ready, labelled data").
POI_LABELS_TR: Dict[POICategory, str] = {
    POICategory.METRO_STATION: "metro istasyonu",
    POICategory.TRAIN_STATION: "tren istasyonu",
    POICategory.HIGHWAY_JUNCTION: "otoyol kavşağı",
    POICategory.UNIVERSITY: "üniversite",
    POICategory.BUS_STOP: "otobüs durağı",
    POICategory.HOSPITAL: "hastane",
    POICategory.SHOPPING_CENTER: "çarşı / AVM",
    POICategory.SCHOOL: "okul",
    POICategory.CITY_CENTER: "şehir merkezi",
    POICategory.PRISON: "cezaevi",
    POICategory.LANDFILL: "çöp sahası",
    POICategory.CEMETERY: "mezarlık",
}
PROJECT_LABELS_TR: Dict[ProjectType, str] = {
    ProjectType.HIGHWAY: "otoyol",
    ProjectType.RAILWAY: "demiryolu hattı",
    ProjectType.INDUSTRIAL_ZONE: "organize sanayi bölgesi",
    ProjectType.PORT: "liman",
}

# Deterministic Turkish free-text -> LandUseProfile keyword mapping. No
# match -> BALANCED + context flags niyet_belirsiz=true, so the system
# prompt can have the model mention the assumption - the LLM is never
# asked to resolve this itself (see the architecture principle: it
# interprets ready numbers, it doesn't make structural decisions about
# what gets computed).
_INTENT_KEYWORDS: Dict[LandUseProfile, List[str]] = {
    LandUseProfile.RESIDENTIAL: ["konut", "ev", "daire", "villa", "site", "yerleşim", "oturmak", "yaşamak"],
    LandUseProfile.COMMERCIAL: ["ticari", "dükkan", "mağaza", "ofis", "iş yeri", "işyeri", "avm", "market", "plaza"],
    LandUseProfile.INDUSTRIAL: ["sanayi", "depo", "lojistik", "fabrika", "atölye", "üretim", "imalat", "antrepo"],
}

_SYSTEM_PROMPT_TEMPLATE = """Sen kullanıcıya kendi şehrini tanımasında yardımcı olan, sıcak ve samimi bir kentsel
büyüme danışmanısın. Kullanıcının seçtiği konum için, SANA VERİLEN sayısal verilere dayanarak
niyetine uygunluğu yorumlarsın. Konuşma dilin sıcak ve yardımsever olsun ama abartılı pazarlama
diline KAÇMA - aşağıdaki kurallar tonundan bağımsız, her zaman geçerlidir.
KURALLAR:
1. YALNIZCA sana verilen alanları kullan. Bir alan null/eksikse 'bu konuma yakın [X] bilgisi
   görünmüyor' de. ASLA mesafe, skor veya özellik UYDURMA.
2. Mesafeleri metre cinsinden NET söyle ('600 metre içinde bir okul var'). 'Yakın/uzak' gibi
   belirsiz ifade KULLANMA; sana verilen rakamı kullan.
3. FİYAT/GETİRİ VAADİ VERME. 'Şu kadar değerlenir', 'kesin iyi yatırım' DEME. Bunun yerine
   niyete UYGUNLUK yorumu yap ('konut için şu yönden uygun, şu yönden zayıf').
4. Büyüme skoru MUTLAK değer değil, göreli bir potansiyel göstergesidir; öyle sun.
5. Hem olumlu hem olumsuz yönleri dengeli belirt. Kısa ve net konuş.

BAĞLAM (JSON):
{context_json}
"""


def map_intent_to_profile(message: str) -> Tuple[LandUseProfile, bool]:
    """Returns (profile, was_ambiguous). Pure keyword matching - no LLM
    call - see the module docstring above for why.
    """
    lowered = message.lower()
    for profile, keywords in _INTENT_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return profile, False
    return LandUseProfile.BALANCED, True


def _nearby_features(context: ScoringContext, lat: float, lon: float) -> List[Dict]:
    """Every real feature within NEARBY_RADIUS_KM, across every category -
    not filtered down to whatever the user's stated intent implies, so
    the same context can answer any follow-up question (see the module
    docstring: this is a chatbot, not a single fixed verdict).

    A category with more than NEARBY_AGGREGATE_THRESHOLD hits collapses
    into one summary entry ({"en_yakin_m": ..., "sayac": ...}) instead of
    listing every one by name+distance - without this, a dense area's
    dozen-odd bus stops turned into a repetitive "524m, 543m, 576m, 620m,
    968m..." wall of numbers in the LLM's reply. Categories at or under the
    threshold stay itemized by name ({"isim": ..., "mesafe_m": ...}) -
    knowing there are 2 schools nearby, and which, is still useful.
    """
    raw_features: List[Dict] = []
    for poi in context.points_of_interest:
        if poi.category not in POI_LABELS_TR:
            continue
        distance_km = haversine_distance_km(lat, lon, poi.latitude, poi.longitude)
        if distance_km <= NEARBY_RADIUS_KM:
            raw_features.append({
                "tur": POI_LABELS_TR[poi.category], "isim": poi.name,
                "mesafe_m": round(distance_km * 1000),
            })
    for project in context.projects:
        if project.project_type not in PROJECT_LABELS_TR:
            continue
        distance_km = haversine_distance_km(lat, lon, project.latitude, project.longitude)
        if distance_km <= NEARBY_RADIUS_KM:
            raw_features.append({
                "tur": PROJECT_LABELS_TR[project.project_type], "isim": project.name,
                "mesafe_m": round(distance_km * 1000),
            })

    by_type: Dict[str, List[Dict]] = defaultdict(list)
    for feature in raw_features:
        by_type[feature["tur"]].append(feature)

    features: List[Dict] = []
    for tur, entries in by_type.items():
        if len(entries) > NEARBY_AGGREGATE_THRESHOLD:
            features.append({
                "tur": tur, "en_yakin_m": min(e["mesafe_m"] for e in entries), "sayac": len(entries),
            })
        else:
            features.extend(entries)

    has_open_land_nearby = any(
        cell.is_open_land and haversine_distance_km(lat, lon, cell.latitude, cell.longitude) <= NEARBY_RADIUS_KM
        for cell in context.land_cover_cells
    )
    if has_open_land_nearby:
        features.append({"tur": "açık/tarım arazisi", "isim": None, "mesafe_m": None})

    features.sort(key=lambda f: f.get("mesafe_m") if f.get("mesafe_m") is not None else f.get("en_yakin_m", 0))
    return features


def _nearest_of_each_type(context: ScoringContext, lat: float, lon: float) -> Dict[str, Optional[int]]:
    """One entry per category REGARDLESS of distance (unlike
    _nearby_features's 1km cutoff) - so the model can always answer "how
    far is the nearest X" even when X is nowhere close. None means the
    city has no ingested data for that category at all (not "far away" -
    a real, honest distinction, see the system prompt's rule 1).
    """
    result: Dict[str, Optional[int]] = {}
    for category, label in POI_LABELS_TR.items():
        pois = context.pois_by_category(category)
        result[label] = (
            round(min(haversine_distance_km(lat, lon, p.latitude, p.longitude) for p in pois) * 1000)
            if pois else None
        )
    for project_type, label in PROJECT_LABELS_TR.items():
        projects = context.projects_by_type(project_type)
        result[label] = (
            round(min(haversine_distance_km(lat, lon, p.latitude, p.longitude) for p in projects) * 1000)
            if projects else None
        )
    return result


def _fringe_label(context: ScoringContext, lat: float, lon: float) -> Optional[str]:
    """Turns FringeContributor's raw multiplier (see
    domain/scoring/contributors/fringe.py - realistic range ~0.85-1.20)
    into a 3-way qualitative label the LLM can use directly rather than
    interpreting a raw multiplier itself. None if no land cover data has
    been ingested yet (see scripts/ingest_sakarya_osm.py) - honestly
    reported as "unknown", not guessed.
    """
    if not context.land_cover_cells or not context.fringe_density_band:
        return None
    probe_region = Region(id=0, name="_advisory_probe", city="", center_lat=lat, center_lon=lon)
    value = FringeContributor().contribute(probe_region, context)
    if value > 1.05:
        return "yuksek"
    if value < 0.95:
        return "dusuk"
    return "orta"


def _growth_direction_info(context: ScoringContext, lat: float, lon: float) -> Optional[dict]:
    """City-wide growth-rate-by-compass-direction (relative to the city's
    overall average - see growth_direction_analysis.compute_sector_growth),
    plus which of those 8 directions the analyzed point itself falls in
    from the city center. Lets the LLM honestly answer "which direction is
    growing fastest" style questions with a real, precomputed figure
    instead of guessing - None (not a fabricated "kuzey") if there's no
    ingested city-center POI or growth-direction data to compute this from.
    """
    if not context.growth_direction_sectors:
        return None
    city_centers = [p for p in context.points_of_interest if p.category == POICategory.CITY_CENTER]
    if not city_centers:
        return None
    center = city_centers[0]

    sectors = context.growth_direction_sectors
    num_sectors = len(sectors)
    by_direction = {
        COMPASS_SECTOR_LABELS_TR[i]: round(sectors[i], 4)
        for i in range(min(num_sectors, len(COMPASS_SECTOR_LABELS_TR)))
    }
    bearing = bearing_degrees(center.latitude, center.longitude, lat, lon)
    point_sector = round(bearing / (360.0 / num_sectors)) % num_sectors
    return {
        "sehir_ortalamasina_gore_yon_bazli_buyume_farki": by_direction,
        "bu_noktanin_sehir_merkezine_gore_yonu": COMPASS_SECTOR_LABELS_TR[point_sector],
    }


def _build_context_dict(
    message: str, profile: LandUseProfile, ambiguous: bool, score: float,
    context: ScoringContext, lat: float, lon: float, mahalle_name: Optional[str],
) -> dict:
    return {
        "kullanici_niyeti": message,
        "kullanilan_profil": profile.value,
        "niyet_belirsiz": ambiguous,
        "mahalle_adi": mahalle_name,
        "buyume_skoru": round(score, 3),
        "yakindaki_ozellikler_1km": _nearby_features(context, lat, lon),
        "en_yakin_metre": _nearest_of_each_type(context, lat, lon),
        "fringe_sinyali": _fringe_label(context, lat, lon),
        "buyume_yonu_analizi": _growth_direction_info(context, lat, lon),
    }


def build_system_prompt(context_dict: dict) -> str:
    return _SYSTEM_PROMPT_TEMPLATE.format(context_json=json.dumps(context_dict, ensure_ascii=False, indent=2))


@dataclass
class AdvisoryTurnResult:
    context: dict
    reply: str


class AdvisoryService:
    def __init__(
        self,
        llm_client: IAdvisoryLLMClient,
        heatmap_service_factory: Callable[[LandUseProfile], HeatmapService],
        # Optional (defaults to None, existing/test call sites unaffected)
        # so a real mahalle name can be resolved when a district_repo is
        # wired in (see core/di.py) - typed directly against the concrete
        # PostGIS repository, same reasoning as DistrictService: this is a
        # read/visualization lookup, not a domain use case.
        district_repo: Optional[SqlAlchemyDistrictBoundaryRepository] = None,
    ):
        self._llm_client = llm_client
        self._heatmap_service_factory = heatmap_service_factory
        self._district_repo = district_repo

    def start_conversation(self, city: str, lat: float, lon: float, message: str) -> AdvisoryTurnResult:
        """First message for a newly-selected point - builds the full
        context (the expensive part, ~5s, see
        HeatmapService.score_point_with_context) once. The returned
        `context` should be sent back by the caller on every subsequent
        continue_conversation() call for the same point, so later
        messages don't repeat that cost (see AdvisoryService's module
        docstring and the API layer's two-endpoint split).
        """
        profile, ambiguous = map_intent_to_profile(message)
        heatmap_service = self._heatmap_service_factory(profile)
        score, scoring_context = heatmap_service.score_point_with_context(city, lat, lon)

        mahalle_name = None
        if self._district_repo is not None:
            mahalle_name = self._district_repo.find_mahalle_names_for_points(city, [(lat, lon)])[0]

        context_dict = _build_context_dict(
            message, profile, ambiguous, score, scoring_context, lat, lon, mahalle_name
        )
        conversation = [{"role": "user", "content": message}]
        reply = self._llm_client.ask(build_system_prompt(context_dict), conversation)
        return AdvisoryTurnResult(context=context_dict, reply=reply)

    def continue_conversation(self, context_dict: dict, conversation: List[Dict[str, str]]) -> str:
        """Fast path - no re-scoring, just another LLM call reusing the
        context the frontend resends from start_conversation()'s response.
        """
        return self._llm_client.ask(build_system_prompt(context_dict), conversation)
