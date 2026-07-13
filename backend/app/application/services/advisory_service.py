"""Orchestrates the point-advisory chatbot: user picks a spot on the map
and a message, gets a reply from an LLM that only interprets numbers this
backend already computed - the LLM never calculates a distance or a score
itself (see IAdvisoryLLMClient's docstring for why that boundary matters).
"""

import json
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
from app.domain.scoring.scoring_context import ScoringContext

NEARBY_RADIUS_KM = 1.0

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

_SYSTEM_PROMPT_TEMPLATE = """Sen bir kentsel büyüme danışmanısın. Kullanıcının seçtiği konum için, SANA VERİLEN sayısal
verilere dayanarak niyetine uygunluğu yorumlarsın.
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
    """
    features = []
    for poi in context.points_of_interest:
        if poi.category not in POI_LABELS_TR:
            continue
        distance_km = haversine_distance_km(lat, lon, poi.latitude, poi.longitude)
        if distance_km <= NEARBY_RADIUS_KM:
            features.append({
                "tur": POI_LABELS_TR[poi.category], "isim": poi.name,
                "mesafe_m": round(distance_km * 1000),
            })
    for project in context.projects:
        if project.project_type not in PROJECT_LABELS_TR:
            continue
        distance_km = haversine_distance_km(lat, lon, project.latitude, project.longitude)
        if distance_km <= NEARBY_RADIUS_KM:
            features.append({
                "tur": PROJECT_LABELS_TR[project.project_type], "isim": project.name,
                "mesafe_m": round(distance_km * 1000),
            })
    has_open_land_nearby = any(
        cell.is_open_land and haversine_distance_km(lat, lon, cell.latitude, cell.longitude) <= NEARBY_RADIUS_KM
        for cell in context.land_cover_cells
    )
    if has_open_land_nearby:
        features.append({"tur": "açık/tarım arazisi", "isim": None, "mesafe_m": None})

    features.sort(key=lambda f: f["mesafe_m"] if f["mesafe_m"] is not None else 0)
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


def _build_context_dict(
    message: str, profile: LandUseProfile, ambiguous: bool, score: float,
    context: ScoringContext, lat: float, lon: float,
) -> dict:
    return {
        "kullanici_niyeti": message,
        "kullanilan_profil": profile.value,
        "niyet_belirsiz": ambiguous,
        "buyume_skoru": round(score, 3),
        "yakindaki_ozellikler_1km": _nearby_features(context, lat, lon),
        "en_yakin_metre": _nearest_of_each_type(context, lat, lon),
        "fringe_sinyali": _fringe_label(context, lat, lon),
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
    ):
        self._llm_client = llm_client
        self._heatmap_service_factory = heatmap_service_factory

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

        context_dict = _build_context_dict(message, profile, ambiguous, score, scoring_context, lat, lon)
        conversation = [{"role": "user", "content": message}]
        reply = self._llm_client.ask(build_system_prompt(context_dict), conversation)
        return AdvisoryTurnResult(context=context_dict, reply=reply)

    def continue_conversation(self, context_dict: dict, conversation: List[Dict[str, str]]) -> str:
        """Fast path - no re-scoring, just another LLM call reusing the
        context the frontend resends from start_conversation()'s response.
        """
        return self._llm_client.ask(build_system_prompt(context_dict), conversation)
