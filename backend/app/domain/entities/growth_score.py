from dataclasses import dataclass


@dataclass
class GrowthScore:
    region_id: int
    raw_score: float
    normalized_score: float = 0.0
