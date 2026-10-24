"""Bounded public web research request and grounded response."""
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class WebResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=600)
    max_sources: int = Field(default=4, ge=1, le=5)


class WebResearchSource(BaseModel):
    citation: str
    title: str
    url: str
    excerpt: str
    published_date: str | None = None


class WebResearchResponse(BaseModel):
    question: str
    answer: str
    sources: list[WebResearchSource]
    provider_name: str
    model_name: str
    searched_at: datetime
