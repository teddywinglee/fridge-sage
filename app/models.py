from datetime import date, datetime

from pydantic import BaseModel, Field


class ItemCreate(BaseModel):
    name: str
    category: str | None = None
    quantity: int = 1
    unit: str | None = None
    expires_at: date
    notes: str | None = None


class ItemUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    quantity: int | None = None
    unit: str | None = None
    expires_at: date | None = None
    notes: str | None = None


class ItemResponse(BaseModel):
    id: str
    name: str
    category: str | None
    quantity: int
    unit: str | None
    stored_at: datetime
    expires_at: date
    notes: str | None
    is_expired: bool
    days_until_expiry: int
    created_at: datetime
    updated_at: datetime


class ExtendRequest(BaseModel):
    days: int = Field(gt=0)


class EventResponse(BaseModel):
    id: int
    item_id: str | None
    event_type: str
    payload: dict
    created_at: datetime


class SearchResult(BaseModel):
    item: ItemResponse
    score: float


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class AskResponse(BaseModel):
    answer: str
    sources: list[str] = Field(default_factory=list, description="IDs of items used as context")
