import json

import openai
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from app.models import IngestRequest, IngestResponse
from app.services import ingest_service

router = APIRouter(prefix="/api/v1/ingest", tags=["ingest"])


@router.post("", status_code=201)
def ingest_text(data: IngestRequest) -> IngestResponse:
    try:
        return ingest_service.ingest(data)
    except openai.APIConnectionError:
        raise HTTPException(
            status_code=503,
            detail="Ingest service unavailable. Is the local LLM server running at the configured URL?",
        )
    except openai.APIError as e:
        raise HTTPException(status_code=502, detail=f"Ingest service error: {e.message}")
    except (json.JSONDecodeError, ValueError) as e:
        raise HTTPException(status_code=422, detail=f"LLM returned unparseable output: {e}")
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=f"LLM output failed validation: {e}")
