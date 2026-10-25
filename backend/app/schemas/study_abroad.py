"""Strict student profile inputs; no sensitive identity numbers."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.study_abroad.workflows import STATES, WORKFLOWS, TOPICS

class StudyCaseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    workflow: Literal["student"] = "student"
    nationality: str = Field(min_length=2, max_length=80)
    residence_country: str = Field(min_length=2, max_length=80)
    destination_country: str = Field(min_length=2, max_length=80)
    degree_level: str = Field(min_length=2, max_length=80)
    study_field: str = Field(min_length=2, max_length=120)
    intake: str = Field(min_length=2, max_length=80)
    @field_validator("nationality","residence_country","destination_country",
      "degree_level","study_field","intake")
    @classmethod
    def normalize_text(cls, text: str) -> str:
        result = " ".join(text.split())
        if len(result) < 2 or any(ord(ch)<32 for ch in result):
            raise ValueError("Enter a valid value")
        return result

class StudyCaseUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    stage: str | None = Field(default=None, max_length=32)
    notes: str | None = Field(default=None, max_length=2000)
    @field_validator("stage")
    @classmethod
    def validate_stage(cls, stage: str | None) -> str | None:
        if stage is not None and stage not in WORKFLOWS["student"].stages:
            raise ValueError("Invalid student journey stage")
        return stage

class StudyChecklistUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str = Field(max_length=28)
    evidence_url: str | None = Field(default=None, max_length=2048)
    @field_validator("state")
    @classmethod
    def validate_state(cls, value: str) -> str:
        if value not in STATES:
            raise ValueError("Invalid checklist state")
        return value

class StudyCaseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    workflow: str
    nationality: str
    residence_country: str
    destination_country: str
    degree_level: str
    study_field: str
    intake: str
    stage: str
    notes: str
    checklist: dict
    created_at: datetime
    updated_at: datetime

class StudyDocumentLink(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(min_length=1, max_length=255)
    checklist_key: str = Field(min_length=2, max_length=50)

class StudyDocumentResponse(BaseModel):
    document_id: str
    filename: str
    status: str
    checklist_key: str

class StudyResearchCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    topic: Literal["universities","admissions","scholarships","visa","embassy","predeparture"]
    confirm_share_profile: bool = False

class StudyResearchResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    topic: str
    question: str
    answer: str
    sources: list
    searched_at: datetime
    verification_status: Literal["needs_official_verification"] = "needs_official_verification"

class UniversityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=160)
    program: str = Field(min_length=2, max_length=160)
    program_url: str = Field(min_length=12, max_length=2048)
    deadline: str = Field(default="", max_length=20)
    notes: str = Field(default="", max_length=1000)

class UniversityStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    application_status: Literal["researching", "shortlisted", "applied", "offer", "declined", "rejected"]

class UniversityResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    case_id: str
    name: str
    program: str
    program_url: str
    deadline: str
    notes: str
    application_status: str
    created_at: datetime
