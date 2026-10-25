"""Bounded, authenticated research requests with explicit opt-in modes."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WebResearchMode = Literal["search", "deep", "compare", "fact_check", "url"]


class WebResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=600)
    max_sources: int = Field(default=4, ge=1, le=5)
    mode: WebResearchMode = "search"
    source_url: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def check_mode_and_url(self):
        if self.mode == "url" and not self.source_url:
            raise ValueError("A public HTTPS URL is required for URL research")
        if self.mode != "url" and self.source_url is not None:
            raise ValueError("source_url is only allowed in URL research")
        return self


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
