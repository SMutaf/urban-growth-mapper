"""Proves the advisory chatbot's core promise: the LLM only ever sees
numbers this backend already computed - nothing is invented, and anything
missing is reported as null rather than guessed. A mock IAdvisoryLLMClient
records exactly what context it was handed so we can assert on it directly,
without needing a real Ollama server or a database.
"""

from typing import Dict, List

import pytest

from app.application.services.advisory_service import (
    AdvisoryService,
    map_intent_to_profile,
)
from app.domain.entities.land_use_profile import LandUseProfile
from app.domain.entities.point_of_interest import POICategory, PointOfInterest
from app.domain.entities.project import ProjectStatus
from app.domain.geo_utils import haversine_distance_km
from app.domain.interpretation.advisory_interfaces import (
    AdvisoryFeatureDisabledError,
    AdvisoryLLMUnavailableError,
)
from app.domain.interpretation.null_advisory_client import NullAdvisoryLLMClient
from app.domain.scoring.scoring_context import ScoringContext

POINT_LAT, POINT_LON = 40.0, 30.0
STUB_SCORE = 0.7234


class RecordingLLMClient:
    """Fake IAdvisoryLLMClient - just remembers what it was asked and
    returns a canned reply, so the test can inspect the exact system
    prompt/context the AdvisoryService assembled.
    """

    def __init__(self, reply: str = "test reply"):
        self.reply = reply
        self.last_system_prompt: str = ""
        self.last_conversation: List[Dict[str, str]] = []

    def ask(self, system_prompt: str, conversation: List[Dict[str, str]]) -> str:
        self.last_system_prompt = system_prompt
        self.last_conversation = conversation
        return self.reply


class StubHeatmapService:
    """Stands in for HeatmapService.score_point_with_context - returns a
    fixed score and a hand-built ScoringContext instead of hitting a
    database, so AdvisoryService can be tested in isolation.
    """

    def __init__(self, context: ScoringContext, score: float = STUB_SCORE):
        self._context = context
        self._score = score

    def score_point_with_context(self, city: str, lat: float, lon: float):
        return self._score, self._context


def _make_context() -> ScoringContext:
    # ~556m away - inside the 1km "nearby" radius.
    nearby_school = PointOfInterest(
        id=1, name="Test Okulu", category=POICategory.SCHOOL, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=40.005, longitude=30.0,
    )
    # ~140km away - outside the 1km radius, but still the nearest hospital.
    far_hospital = PointOfInterest(
        id=2, name="Uzak Hastane", category=POICategory.HOSPITAL, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=41.0, longitude=31.0,
    )
    # No METRO_STATION POI at all - en_yakin_metre must report None for it,
    # not a fabricated distance.
    return ScoringContext(points_of_interest=[nearby_school, far_hospital])


def _make_service(context: ScoringContext, llm_client: RecordingLLMClient) -> AdvisoryService:
    return AdvisoryService(
        llm_client=llm_client,
        heatmap_service_factory=lambda profile: StubHeatmapService(context),
    )


def test_nearby_school_distance_matches_computed_haversine_exactly():
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    nearby = result.context["yakindaki_ozellikler_1km"]
    school_entry = next(f for f in nearby if f["tur"] == "okul")
    expected_m = round(haversine_distance_km(POINT_LAT, POINT_LON, 40.005, 30.0) * 1000)
    assert school_entry["mesafe_m"] == expected_m
    assert school_entry["isim"] == "Test Okulu"


def test_far_poi_excluded_from_nearby_but_present_in_nearest():
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    nearby_types = [f["tur"] for f in result.context["yakindaki_ozellikler_1km"]]
    assert "hastane" not in nearby_types

    expected_m = round(haversine_distance_km(POINT_LAT, POINT_LON, 41.0, 31.0) * 1000)
    assert result.context["en_yakin_metre"]["hastane"] == expected_m


def test_missing_category_reported_as_null_not_fabricated():
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    assert result.context["en_yakin_metre"]["metro istasyonu"] is None


def test_missing_land_cover_reports_fringe_signal_as_null():
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    assert result.context["fringe_sinyali"] is None


def test_missing_growth_direction_data_reports_null_not_fabricated():
    # _make_context() has no city_center POI and no growth_direction_sectors -
    # a "which direction is growing fastest" question must be answerable as
    # "unknown", not with an invented direction.
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    assert result.context["buyume_yonu_analizi"] is None


def test_growth_direction_info_uses_real_precomputed_sector_data():
    city_center = PointOfInterest(
        id=3, name="Sehir Merkezi", category=POICategory.CITY_CENTER, status=ProjectStatus.COMPLETED,
        city="sakarya", latitude=POINT_LAT, longitude=POINT_LON,
    )
    # 8 sectors, index 0 = north - only north is non-zero here.
    sectors = [0.05, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
    context = ScoringContext(points_of_interest=[city_center], growth_direction_sectors=sectors)
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    # Due north of the city center.
    analyzed_lat, analyzed_lon = POINT_LAT + 0.1, POINT_LON

    result = service.start_conversation("sakarya", analyzed_lat, analyzed_lon, "buraya konut yapmak istiyorum")

    direction_info = result.context["buyume_yonu_analizi"]
    assert direction_info["bu_noktanin_sehir_merkezine_gore_yonu"] == "kuzey"
    assert direction_info["sehir_ortalamasina_gore_yon_bazli_buyume_farki"]["kuzey"] == 0.05
    assert direction_info["sehir_ortalamasina_gore_yon_bazli_buyume_farki"]["guney"] == 0.0


def test_context_json_sent_to_llm_matches_returned_context_exactly():
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    # Every number the LLM sees in its system prompt must be the same
    # number returned to the caller - no separate, divergent path where
    # the LLM could be shown something different from what's reported.
    import json
    assert json.dumps(result.context, ensure_ascii=False, indent=2) in llm_client.last_system_prompt


def test_ambiguous_intent_falls_back_to_balanced_and_flags_it():
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "bilmiyorum ne yapayım")

    assert result.context["kullanilan_profil"] == LandUseProfile.BALANCED.value
    assert result.context["niyet_belirsiz"] is True


def test_clear_intent_is_not_flagged_ambiguous():
    profile, ambiguous = map_intent_to_profile("depo kurmayı düşünüyorum")
    assert profile == LandUseProfile.INDUSTRIAL
    assert ambiguous is False


def test_continue_conversation_reuses_context_without_rescoring():
    context = _make_context()
    llm_client = RecordingLLMClient(reply="ikinci yanıt")
    service = _make_service(context, llm_client)

    first = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")
    conversation = [
        {"role": "user", "content": "buraya konut yapmak istiyorum"},
        {"role": "assistant", "content": first.reply},
        {"role": "user", "content": "en yakın hastane ne kadar uzakta?"},
    ]

    reply = service.continue_conversation(first.context, conversation)

    assert reply == "ikinci yanıt"
    assert llm_client.last_conversation == conversation
    # The follow-up turn must reuse the exact same context, not silently
    # recompute (and potentially diverge) it.
    import json
    assert json.dumps(first.context, ensure_ascii=False, indent=2) in llm_client.last_system_prompt


def test_dense_category_collapses_into_nearest_plus_count():
    # 4 bus stops within 1km - above NEARBY_AGGREGATE_THRESHOLD (3) - must
    # collapse into one summary entry instead of 4 separate "isim"/"mesafe_m"
    # entries (the "524m, 543m, 576m, 620m" wall-of-numbers problem).
    bus_stops = [
        PointOfInterest(
            id=i, name=f"Durak {i}", category=POICategory.BUS_STOP, status=ProjectStatus.COMPLETED,
            city="sakarya", latitude=POINT_LAT + i * 0.001, longitude=POINT_LON,
        )
        for i in range(1, 5)
    ]
    context = ScoringContext(points_of_interest=bus_stops)
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    nearby = result.context["yakindaki_ozellikler_1km"]
    bus_entries = [f for f in nearby if f["tur"] == "otobüs durağı"]
    assert len(bus_entries) == 1
    assert "isim" not in bus_entries[0]
    assert bus_entries[0]["sayac"] == 4
    expected_nearest_m = round(haversine_distance_km(POINT_LAT, POINT_LON, POINT_LAT + 0.001, POINT_LON) * 1000)
    assert bus_entries[0]["en_yakin_m"] == expected_nearest_m


def test_sparse_category_stays_itemized_by_name():
    # Only 2 schools within 1km - at/under the threshold - must stay listed
    # individually by name, not collapsed.
    schools = [
        PointOfInterest(
            id=1, name="Okul A", category=POICategory.SCHOOL, status=ProjectStatus.COMPLETED,
            city="sakarya", latitude=POINT_LAT + 0.001, longitude=POINT_LON,
        ),
        PointOfInterest(
            id=2, name="Okul B", category=POICategory.SCHOOL, status=ProjectStatus.COMPLETED,
            city="sakarya", latitude=POINT_LAT + 0.002, longitude=POINT_LON,
        ),
    ]
    context = ScoringContext(points_of_interest=schools)
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    school_entries = [f for f in result.context["yakindaki_ozellikler_1km"] if f["tur"] == "okul"]
    assert {e["isim"] for e in school_entries} == {"Okul A", "Okul B"}
    assert all("sayac" not in e for e in school_entries)


def test_mahalle_name_is_null_without_a_district_repo():
    # _make_service doesn't wire a district_repo - reverse-geocoding a
    # mahalle name must degrade to null, not crash or guess.
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = _make_service(context, llm_client)

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    assert result.context["mahalle_adi"] is None


class StubDistrictRepo:
    """Fake SqlAlchemyDistrictBoundaryRepository - just returns a canned
    mahalle name for find_mahalle_names_for_points, no real DB/geometry.
    """

    def __init__(self, name):
        self._name = name

    def find_mahalle_names_for_points(self, city, points):
        return [self._name for _ in points]


def test_mahalle_name_populated_when_district_repo_resolves_it():
    context = _make_context()
    llm_client = RecordingLLMClient()
    service = AdvisoryService(
        llm_client=llm_client,
        heatmap_service_factory=lambda profile: StubHeatmapService(context),
        district_repo=StubDistrictRepo("Test Mahallesi"),
    )

    result = service.start_conversation("sakarya", POINT_LAT, POINT_LON, "buraya konut yapmak istiyorum")

    assert result.context["mahalle_adi"] == "Test Mahallesi"


def test_null_client_raises_disabled_error_never_returns_empty_reply():
    client = NullAdvisoryLLMClient()
    with pytest.raises(AdvisoryFeatureDisabledError):
        client.ask("system prompt", [{"role": "user", "content": "merhaba"}])


def test_unreachable_ollama_raises_unavailable_error(monkeypatch):
    from app.infrastructure.llm.ollama_advisory_client import OllamaAdvisoryClient
    import requests

    def _raise_connection_error(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr(requests, "post", _raise_connection_error)
    client = OllamaAdvisoryClient(base_url="http://localhost:11434", model="gemma3:12b", temperature=0.3)

    with pytest.raises(AdvisoryLLMUnavailableError):
        client.ask("system prompt", [{"role": "user", "content": "merhaba"}])
