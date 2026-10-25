"""Bounded, authenticated research requests with explicit opt-in modes."""
from datetime import datetime
from typing import Literal
import ipaddress
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

WebResearchMode = Literal["search", "deep", "compare", "fact_check", "url"]
WebResearchTimeRange = Literal["day", "week", "month", "year"]

DOMAIN_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$")


def normalize_research_domain(domain: str) -> str:
    value = domain.strip().lower().rstrip(".")
    if not DOMAIN_PATTERN.fullmatch(value) or len(value) > 253:
        raise ValueError("Enter a hostname such as docs.python.org (no scheme, path or wildcard)")
    if value.endswith((".local", ".localhost", ".internal", ".test", ".invalid")):
        raise ValueError("Internal hosts are not allowed")
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return value
    raise ValueError("IP addresses are not supported as research domains")



class WebResearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=3, max_length=600)
    max_sources: int = Field(default=4, ge=1, le=5)
    mode: WebResearchMode = "search"
    source_url: str | None = Field(default=None, max_length=2048)
    time_range: WebResearchTimeRange | None = None
    include_domains: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("include_domains")
    @classmethod
    def validate_domains(cls, domains: list[str]) -> list[str]:
        normalized = [normalize_research_domain(domain) for domain in domains]
        if len(set(normalized)) != len(normalized):
            raise ValueError("Duplicate domains are not allowed")
        return normalized

    @model_validator(mode="after")
    def check_mode_and_url(self):
        if self.mode == "url" and (self.time_range is not None or self.include_domains):
            raise ValueError("URL mode cannot include search-time or domain filters")
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
