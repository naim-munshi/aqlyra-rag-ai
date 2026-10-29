"""Extensible workflows. These are suggested checks, NOT visa requirements."""
from dataclasses import dataclass

@dataclass(frozen=True)
class Workflow:
    key: str
    title: str
    enabled: bool
    stages: tuple[str, ...]

WORKFLOWS = {
 "student": Workflow("student", "Study Abroad — Student Visa", True,
  ("profile", "university", "admission", "documents", "scholarship", "visa", "embassy", "predeparture")),
 "job": Workflow("job", "Job Visa — future", False,
  ("profile", "employer", "offer", "work_authorization", "embassy")),
}
TOPICS = {
 "universities": "Find genuine universities and OFFICIAL course/admissions pages matching the desired field and degree. Identify official tuition and language requirements if supported.",
 "admissions": "Research official program eligibility, academic transcripts, test scores, application process and deadlines. Varies by university.",
 "scholarships": "Find official scholarship websites, conditional eligibility, deadlines and fees. Never promise awards.",
 "visa": "Research the government's official student immigration/visa rules and conditional required documents for this NATIONALITY and RESIDENCE, including financial, health and language conditions.",
 "embassy": "Find the responsible diplomatic mission for the applicant's RESIDENCE, appointment process, visa category, official document guidance and mission website. Do not claim a real appointment is available.",
 "predeparture": "Research official insurance, residence registration, work permission and arrival rules for the destination. Explain which rules depend on the permit.",
}
CHECKS = (
 ("passport", "Passport / travel document"),
 ("academic", "Academic certificates and transcripts"),
 ("language", "Language proficiency evidence"),
 ("application", "University application"),
 ("admission", "Offer / enrollment evidence"),
 ("finances", "Funding / sponsorship documents"),
 ("translations", "Certified translations if applicable"),
 ("health", "Health / insurance checks if applicable"),
 ("visa", "Visa / residence permission"),
 ("appointment", "Consular appointment if applicable"),
)
STATES = frozenset(("needs_verification", "not_started", "in_progress", "uploaded", "reviewed", "not_applicable"))

def initial_checklist() -> dict:
    return {key: {"title": title, "state": "needs_verification", "evidence_url": None, "document_id": None} for key,title in CHECKS}

def research_question(topic: str, case: object) -> str:
    if topic not in TOPICS:
        raise ValueError("Unknown research topic")
    prefix = (f"Nationality: {case.nationality}. Current residence: {case.residence_country}. "
       f"Target country: {case.destination_country}. Degree: {case.degree_level}. "
       f"Field: {case.study_field}. Intake: {case.intake}. ")
    return (prefix + TOPICS[topic] + " Provide source citations, publication dates when available, and identify unknown requirements.")[:600]
