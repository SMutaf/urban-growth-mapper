from typing import List, Optional

from app.domain.entities.growth_score import GrowthScore
from app.domain.entities.project import Project


class NullLLMInterpreter:
    """Default Null Object implementation of ILLMInterpreter.

    Used until a real LLM provider is wired in. Keeps HeatmapService free of
    None-checks and free of any dependency on a specific LLM SDK.
    """

    def interpret(self, scores: List[GrowthScore], projects: List[Project]) -> Optional[str]:
        return None
