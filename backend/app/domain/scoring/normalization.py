from typing import List

from app.domain.entities.growth_score import GrowthScore


def normalize_scores(scores: List[GrowthScore]) -> List[GrowthScore]:
    """Min-max normalizes raw_score into normalized_score, in [0, 1]."""
    if not scores:
        return []
    values = [s.raw_score for s in scores]
    min_value, max_value = min(values), max(values)
    span = (max_value - min_value) or 1.0
    return [
        GrowthScore(
            region_id=s.region_id,
            raw_score=s.raw_score,
            normalized_score=(s.raw_score - min_value) / span,
        )
        for s in scores
    ]
