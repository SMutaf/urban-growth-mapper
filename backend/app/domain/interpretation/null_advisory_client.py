from typing import Dict, List

from app.domain.interpretation.advisory_interfaces import AdvisoryFeatureDisabledError


class NullAdvisoryLLMClient:
    """Default Null Object implementation of IAdvisoryLLMClient - wired in
    when Settings.advisory_llm_enabled is False (see app/core/di.py).
    Always raises rather than returning an empty/fake reply, so a disabled
    feature and a broken one both surface honestly to the end user instead
    of looking like a silent no-op.
    """

    def ask(self, system_prompt: str, conversation: List[Dict[str, str]]) -> str:
        raise AdvisoryFeatureDisabledError(
            "Danışma sohbeti şu an devre dışı (advisory_llm_enabled=False)."
        )
