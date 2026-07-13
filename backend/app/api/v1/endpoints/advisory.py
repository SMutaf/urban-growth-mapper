from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_advisory_service
from app.application.services.advisory_service import AdvisoryService
from app.domain.interpretation.advisory_interfaces import AdvisoryError

router = APIRouter()


class AdvisoryStartRequest(BaseModel):
    city: str
    lat: float
    lon: float
    message: str


class AdvisoryStartResponse(BaseModel):
    used_profile: str
    context: dict
    advice: str


class AdvisoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class AdvisoryChatRequest(BaseModel):
    # The exact `context` dict returned by POST /advisory - the frontend
    # resends it so this endpoint never has to re-run the ~5s city-wide
    # scoring pass just to keep chatting about the same point (see
    # HeatmapService.score_point_with_context and AdvisoryService's module
    # docstring for why that pass is expensive and why it's only paid once).
    context: dict
    conversation: List[AdvisoryMessage]


class AdvisoryChatResponse(BaseModel):
    advice: str


@router.post("/advisory", response_model=AdvisoryStartResponse)
def start_advisory(
    request: AdvisoryStartRequest, service: AdvisoryService = Depends(get_advisory_service)
):
    """First message for a newly-selected map point. Builds the full
    context (nearby features, growth score under the intent-matched
    profile, fringe signal) and returns it alongside the LLM's first
    reply - the frontend should hold onto `context` and pass it back to
    POST /advisory/chat for follow-up questions about the same point.
    """
    try:
        result = service.start_conversation(request.city, request.lat, request.lon, request.message)
    except AdvisoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdvisoryStartResponse(
        used_profile=result.context["kullanilan_profil"], context=result.context, advice=result.reply
    )


@router.post("/advisory/chat", response_model=AdvisoryChatResponse)
def continue_advisory(
    request: AdvisoryChatRequest, service: AdvisoryService = Depends(get_advisory_service)
):
    """Follow-up messages for a point already opened via POST /advisory -
    fast (no re-scoring), just another LLM call over the same context.
    """
    try:
        conversation = [{"role": m.role, "content": m.content} for m in request.conversation]
        reply = service.continue_conversation(request.context, conversation)
    except AdvisoryError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return AdvisoryChatResponse(advice=reply)
