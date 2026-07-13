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
