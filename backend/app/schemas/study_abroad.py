"""Strict student profile inputs; no sensitive identity numbers."""
from datetime import datetime
import re
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
    topic: Literal["universities","admissions","scholarships","visa","embassy","predeparture","language","costs","transfer"]
    confirm_share_profile: bool = False
    focus_university_id: str | None = Field(default=None, min_length=1, max_length=64)
    specific_question: str | None = Field(default=None, min_length=12, max_length=160)

    @field_validator("specific_question")
    @classmethod
    def validate_specific_question(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if len(cleaned) < 12:
            raise ValueError("Specific question is too short")
        # Do not send links, email addresses or long identity/account
        # numbers to public external research on the applicant's behalf.
        if (re.search(r"https?://|www\.", cleaned, re.I)
                or re.search(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", cleaned)
                or re.search(r"(?<!\d)\d{9,}(?!\d)", cleaned)
                or any(ord(ch) < 32 for ch in cleaned)):
            raise ValueError(
                "Do not put links, email addresses or identity/account numbers "
                "in public study research questions"
            )
        return cleaned

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

class StudyDocumentQuestion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str = Field(min_length=5, max_length=1200)
    confirm_share_documents: bool = False

class StudyDocumentCitation(BaseModel):
    source_id: str
    document_id: str
    filename: str
    source_label: str
    excerpt: str

class StudyDocumentAnswer(BaseModel):
    question: str
    answer: str
    is_refusal: bool
    citations: list[StudyDocumentCitation]
    searched_document_count: int
    note: str = "Only attached documents were consulted; this is not official visa or admission verification."


class StudyAdvisorAction(BaseModel):
    id: str
    title: str
    reason: str
    urgency: Literal["urgent", "next", "later"]
    research_topic: str | None = None
    university_id: str | None = None


class StudyAdvisorResearchSnapshot(BaseModel):
    topic: str
    searched_at: str
    age_days: int
    stale: bool
    government_domain_sources: int
    source_count: int
    verification_status: Literal["needs_official_verification"]


class StudyAdvisorDeadline(BaseModel):
    university_id: str
    university_name: str
    user_entered_deadline: str
    days_remaining: int
    urgency: Literal["past", "soon"]
    verification_status: Literal["user_entered_unverified"]


class StudyAdvisorResponse(BaseModel):
    case_id: str
    reviewed_checklist_count: int
    not_applicable_count: int
    total_checklist_count: int
    linked_document_count: int
    shortlisted_university_count: int
    research_freshness: list[StudyAdvisorResearchSnapshot]
    deadline_warnings: list[StudyAdvisorDeadline]
    next_actions: list[StudyAdvisorAction]
    generated_at: str
    verification_status: Literal["planning_only_not_eligibility_verified"]
    disclaimer: str
