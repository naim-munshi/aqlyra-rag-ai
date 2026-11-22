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
 "language": "Check official degree-specific language of instruction, acceptable tests, required score thresholds and exemption rules. If official evidence is absent, state unknown rather than inventing scores.",
 "costs": "Research official university tuition/fees and published government/student services living-cost guidance; distinguish fees from estimated living expenses and identify uncertain or dated figures.",
 "transfer": "Check university-published transfer admissions, credit recognition, second/third-year entry, qualifying prior study, entrance exams and application windows. Never assume credits transfer or admission is available.",

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

def research_question(topic: str, case: object, focus: tuple[str, str] | None = None, specific_question: str | None = None) -> str:
    if topic not in TOPICS:
        raise ValueError("Unknown research topic")
    prefix = (f"Nationality: {case.nationality}. Current residence: {case.residence_country}. "
       f"Target country: {case.destination_country}. Degree: {case.degree_level}. "
       f"Field: {case.study_field}. Intake: {case.intake}. ")
    focus_text = (f" Focus university: {focus[0][:120]}; program: {focus[1][:120]}. "
                  if focus else "")
    suffix = " Cite live sources, report dates when available, and state unknowns; do not guarantee eligibility."
    # A specific question is opt-in and must be kept intact in the request.
    # Truncate only optional public profile labels to fit the 600-char
    # provider budget; never send private documents or university URL tokens.
    if specific_question:
        compact = (
            f"Nationality: {str(case.nationality)[:32]}. "
            f"Residence: {str(case.residence_country)[:32]}. "
            f"Destination: {str(case.destination_country)[:32]}. "
            f"Degree: {str(case.degree_level)[:32]}. "
            f"Field: {str(case.study_field)[:48]}. "
            f"Intake: {str(case.intake)[:24]}. "
        )
        targeted = (f" University: {focus[0][:45]}; program: {focus[1][:45]}."
                    if focus else "")
        question_text = f" User's focused question: {specific_question}."
        required_length = len(question_text) + len(suffix)
        context_budget = max(0, 600 - required_length)
        return (compact + targeted)[:context_budget] + question_text + suffix
    # Research provider accepts at most 600 characters; never cut away the safety suffix.
    return (prefix + focus_text + TOPICS[topic])[:600 - len(suffix)] + suffix
