from typing import List, Optional, Protocol

from app.domain.entities.growth_score import GrowthScore
from app.domain.entities.project import Project


class ILLMInterpreter(Protocol):
    """Port for turning growth scores + raw project data into a human-readable
    commentary. Optional by design: the platform must work with NullLLMInterpreter
    and gain no new behavior when a real LLM-backed implementation (Claude, OpenAI,
    a local model...) is swapped in later - only the DI wiring changes.
    """

    def interpret(self, scores: List[GrowthScore], projects: List[Project]) -> Optional[str]:
        ...
