from app.domain.entities.growth_score import GrowthScore
from app.domain.scoring.normalization import normalize_scores


def test_min_maps_to_zero_and_max_to_one():
    scores = [GrowthScore(region_id=1, raw_score=0.5), GrowthScore(region_id=2, raw_score=8.0)]

    normalized = {s.region_id: s.normalized_score for s in normalize_scores(scores)}

    assert normalized[1] == 0.0
    assert normalized[2] == 1.0


def test_an_extreme_outlier_does_not_crush_the_rest_of_the_distribution():
    # Without log-normalization, a single 20x outlier crushes every other
    # region towards 0 under plain linear min-max - this is exactly the
    # "whole map reads as empty/cold except one hot spot" symptom that
    # motivated switching to log-space normalization.
    scores = [
        GrowthScore(region_id=1, raw_score=0.5),
        GrowthScore(region_id=2, raw_score=1.0),
        GrowthScore(region_id=3, raw_score=2.0),
        GrowthScore(region_id=4, raw_score=10.0),
    ]

    normalized = {s.region_id: s.normalized_score for s in normalize_scores(scores)}

    # The "typical" middle region (raw_score=2.0, well above the 0.5 min)
    # should land in a visually meaningful mid-range, not be crushed near 0.
    assert normalized[3] > 0.4


def test_equal_scores_yield_zero_without_dividing_by_zero():
    scores = [GrowthScore(region_id=1, raw_score=1.5), GrowthScore(region_id=2, raw_score=1.5)]

    normalized = normalize_scores(scores)

    assert all(s.normalized_score == 0.0 for s in normalized)


def test_empty_list_returns_empty():
    assert normalize_scores([]) == []
