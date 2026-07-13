from typing import Dict, List, Protocol


class AdvisoryError(Exception):
    """Base for advisory-chat failures - see subclasses for the two
    distinct situations the API layer needs to tell apart and report
    honestly to the user (never silently swallowed into an empty reply).
    """


class AdvisoryFeatureDisabledError(AdvisoryError):
    """Raised by NullAdvisoryLLMClient - the advisory feature is turned
    off via config (Settings.advisory_llm_enabled=False), not broken.
    """


class AdvisoryLLMUnavailableError(AdvisoryError):
    """Raised by a real LLM client (e.g. OllamaAdvisoryClient) when the
    backing service is enabled but unreachable (connection refused,
    timeout, non-2xx response...) - a real failure, distinct from the
    feature being deliberately off.
    """


class IAdvisoryLLMClient(Protocol):
    """Port for the advisory chat's LLM backend (see
    application/services/advisory_service.py). Optional by design, same
    pattern as ILLMInterpreter/NullLLMInterpreter (domain/interpretation/
    interfaces.py) - the platform works with NullAdvisoryLLMClient with no
    behavior change to the rest of the app, only the DI wiring changes to
    swap in a real provider (Ollama today, could be a different model or a
    remote API later without touching AdvisoryService).

    This is a genuinely different shape of problem from ILLMInterpreter
    (which narrates a whole city's batch of pre-computed scores) - this
    one is a single-point, multi-turn, user-driven conversation - so it's
    its own interface rather than a forced reuse of that one.
    """

    def ask(self, system_prompt: str, conversation: List[Dict[str, str]]) -> str:
        """`system_prompt` is the fully-assembled system message (fixed
        instructions + the point's JSON context - see AdvisoryService),
        `conversation` is [{"role": "user"|"assistant", "content": ...},
        ...] oldest-first, ending with the newest user message. Returns
        the assistant's reply text.

        Must raise AdvisoryFeatureDisabledError or
        AdvisoryLLMUnavailableError rather than returning None/"" on
        failure - the API layer surfaces these as a clear error to the
        user instead of a silently empty chat reply.
        """
        ...
