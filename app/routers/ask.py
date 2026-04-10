import openai
from fastapi import APIRouter, HTTPException

from app.models import AskRequest, AskResponse
from app.services import ask_service

router = APIRouter(prefix="/api/v1/ask", tags=["ask"])


@router.post("")
def ask_question(data: AskRequest) -> AskResponse:
    try:
        return ask_service.ask(data)
    except openai.APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Q&A service unavailable. Is the local LLM server running at the configured URL?",
        )
    except openai.APIError as e:
        raise HTTPException(status_code=502, detail=f"Q&A service error: {e.message}")
