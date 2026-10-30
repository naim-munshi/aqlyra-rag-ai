"""Read-only public-browser agent. Each run requires explicit approval."""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

class BrowserPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task: str = Field(min_length=5, max_length=500)
    start_url: str = Field(min_length=12, max_length=2048)

class BrowserPlanResponse(BaseModel):
    plan_token: str
    expires_at: datetime
    task: str
    start_url: str
    allowed_host: str
    max_pages: int
    capabilities: list[str]
    restrictions: list[str]

class BrowserExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan_token: str = Field(min_length=20, max_length=4096)
    approved: bool

class BrowserPageEvidence(BaseModel):
    citation: str
    title: str
    url: str
    excerpt: str

class BrowserRunResponse(BaseModel):
    task: str
    answer: str
    visited: list[BrowserPageEvidence]
    steps: list[str]
    finished_at: datetime
    model_name: str
