import math
from typing import List

from app.domain.entities.growth_score import GrowthScore


def normalize_scores(scores: List[GrowthScore]) -> List[GrowthScore]:
    """Min-max normalizes log(raw_score) into normalized_score, in [0, 1].

    raw_score is a *product* of contributor multipliers (see
    CompositeHeatmapScorer) - an exponential quantity, not a linear one.
    Plain min-max on the raw product is the wrong scale to normalize on: one
    region sitting right at the intersection of several strong positive
    factors (e.g. right next to the CBD, a university, and a train station
    all at once) can multiply out to 5-10x a typical region's score, and
    linear min-max then crushes every other region towards 0 relative to
    that single outlier - in practice this looked like almost the entire
    map reading as "cold" except a small hot core, even though most of the
    variation was actually happening in the "cold" 90% of the range.
    Normalizing log(raw_score) instead (equivalent to summing each
    contributor's log-effect, then min-max on that sum) spreads the
    distribution out proportionally to each factor's real percentage
    effect, which is the natural scale for a multiplicative model.
    """
    if not scores:
        return []
    log_values = [math.log(s.raw_score) for s in scores]
    min_value, max_value = min(log_values), max(log_values)
    span = (max_value - min_value) or 1.0
    return [
        GrowthScore(
            region_id=s.region_id,
            raw_score=s.raw_score,
            normalized_score=(log_value - min_value) / span,
        )
        for s, log_value in zip(scores, log_values)
    ]
