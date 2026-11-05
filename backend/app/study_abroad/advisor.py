"""Explainable study journey guidance derived only from the owner's saved evidence.

No admission/visa eligibility predictions, fabricated school facts, or automatic
external actions. This is a deterministic planning layer, not a legal decision.
"""
from datetime import date, datetime, timezone
from typing import Any

from app.study_abroad.workflows import CHECKS, TOPICS

FRESH_DAYS = 45
MAX_ACTIONS = 6


def _safe_deadline(value: str) -> date | None:
    """Accept only ISO dates; user-entered deadlines are never authoritative."""
    if len(value) != 10:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.isoformat() == value else None


def _report_snapshot(reports: list, now: datetime) -> list[dict[str, Any]]:
    latest: dict[str, Any] = {}
    for report in reports:
        if report.topic not in TOPICS or report.topic in latest:
            continue
        at = report.searched_at
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        age_days = max(0, (now - at).days)
        sources = report.sources if isinstance(report.sources, list) else []
        latest[report.topic] = {
            "topic": report.topic,
            "searched_at": at.isoformat(),
            "age_days": age_days,
            "stale": age_days > FRESH_DAYS,
            # A government-looking hostname is not proof of applicability.
            "government_domain_sources": sum(
                isinstance(s, dict) and
                s.get("source_type") == "official_authority_domain"
                for s in sources
            ),
            "source_count": len(sources),
            "verification_status": "needs_official_verification",
        }
    return [latest[topic] for topic in TOPICS if topic in latest]


def build_study_advisor(
    *, case: Any, universities: list, reports: list,
    linked_document_count: int, now: datetime | None = None,
) -> dict[str, Any]:
    """Case-local summary: planning priorities, not a probability of admission."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    today = current.date()
    checks = case.checklist if isinstance(case.checklist, dict) else {}
    total = len(CHECKS)
    reviewed = sum(
        isinstance(checks.get(k), dict)
        and checks[k].get("state") == "reviewed"
        for k, _ in CHECKS
    )
    not_applicable = sum(
        isinstance(checks.get(k), dict)
        and checks[k].get("state") == "not_applicable"
        for k, _ in CHECKS
    )
    snapshots = _report_snapshot(reports, current)
    by_topic = {r["topic"]: r for r in snapshots}
    deadline_warnings = []
    for u in universities:
        deadline = _safe_deadline((u.deadline or "").strip())
        if deadline is None:
            continue
        delta = (deadline - today).days
        if -365 <= delta <= 60 and u.application_status not in ("rejected", "declined"):
            deadline_warnings.append({
                "university_id": u.id, "university_name": u.name,
                "user_entered_deadline": deadline.isoformat(),
                "days_remaining": delta,
                "urgency": "past" if delta < 0 else "soon",
                "verification_status": "user_entered_unverified",
            })
    deadline_warnings.sort(key=lambda d: (d["days_remaining"], d["university_name"].lower()))
    actions: list[dict[str, Any]] = []
    used: set[str] = set()

    def add(key: str, title: str, reason: str, urgency: str,
            topic: str | None = None, university_id: str | None = None) -> None:
        if key not in used:
            used.add(key)
            actions.append({
                "id": key, "title": title, "reason": reason,
                "urgency": urgency, "research_topic": topic,
                "university_id": university_id,
            })

    for d in deadline_warnings[:2]:
        label = "Deadline may have passed" if d["days_remaining"] < 0 else "Upcoming deadline"
        add(
            "deadline:" + d["university_id"],
            f"{label}: {d['university_name']}",
            f"{d['user_entered_deadline']} is a manually entered date. Verify the current program deadline on the official admissions page before acting.",
            "urgent", "admissions", d["university_id"],
        )
    if not universities:
        add(
            "shortlist", "Find official university programs",
            "No programs are shortlisted yet. Compare exact degrees, language of instruction, eligibility and actual intake on official university sites.",
            "next", "universities",
        )
    elif not any(u.application_status in ("applied", "offer") for u in universities):
        add(
            "eligibility", "Compare admission eligibility",
            "Your saved programs are not recorded as applied/offered. Check the exact academic and language prerequisites for each shortlisted program.",
            "next", "admissions", universities[0].id,
        )
    for topic, title in (
        ("admissions", "Verify current entry requirements"),
        ("language", "Verify language test requirements"),
        ("costs", "Verify tuition and living expenses"),
        ("scholarships", "Check official scholarship eligibility"),
        ("visa", "Check current student immigration guidance"),
    ):
        snapshot = by_topic.get(topic)
        if snapshot is None or snapshot["stale"]:
            reason = (
                "No dated source-based research is saved for this topic."
                if snapshot is None
                else f"The latest source snapshot is {snapshot['age_days']} days old. Verify changes at the official provider."
            )
            add("research:" + topic, title, reason, "next", topic)
    if linked_document_count == 0:
        add(
            "documents", "Link documents for private evidence-based answers",
            "No ready private document is attached to this journey. Files remain in your private document library and are shared with the AI only after consent.",
            "later",
        )
    if reviewed < total:
        pending = [title for key, title in CHECKS if not (
            isinstance(checks.get(key), dict)
            and checks[key].get("state") in ("reviewed", "not_applicable")
        )]
        if pending:
            add("checklist", "Review outstanding checklist items",
                "Start with " + ", ".join(pending[:2]) +
                ". The checklist is a planning aid; confirm official country/program requirements.",
                "later")
    if not actions:
        add(
            "recheck", "Recheck official sources before submission",
            "Manual review and older research never guarantee admission, visa issuance or an appointment.",
            "later",
        )
    rank = {"urgent": 0, "next": 1, "later": 2}
    actions.sort(key=lambda a: rank[a["urgency"]])
    return {
        "case_id": case.id,
        "reviewed_checklist_count": reviewed,
        "not_applicable_count": not_applicable,
        "total_checklist_count": total,
        "linked_document_count": linked_document_count,
        "shortlisted_university_count": len(universities),
        "research_freshness": snapshots,
        "deadline_warnings": deadline_warnings[:5],
        "next_actions": actions[:MAX_ACTIONS],
        "generated_at": current.isoformat(),
        "verification_status": "planning_only_not_eligibility_verified",
        "disclaimer": (
            "Suggested steps use your saved case and research snapshots. "
            "Checklist statuses and deadlines are user-entered, not officially verified. "
            "Aqlyra does not predict admission or visa decisions."
        ),
    }
