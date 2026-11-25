"""Keep Study Abroad checklist snapshots aligned with original file deletion.

Do not independently commit. Caller must delete the Document in the SAME
PostgreSQL transaction as these owner-scoped checklist updates; cascading
study_case_documents link deletion then becomes atomic with the snapshot.
No raw file bytes, object keys, credentials or third-party services.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import utc_now_naive
from app.models.document import Document
from app.models.study_case import StudyCase, StudyCaseDocument


class StudyDocumentIntegrityError(ValueError):
    """Existing study association is not consistent with the file owner."""


def reconcile_document_before_delete(
    *, db: Session, document: Document,
) -> int:
    """Remove references to the soon-to-be-deleted source document.

    Returns number of affected study cases; never deletes/commits on its
    own. Locks case records in stable order and deliberately fails closed
    on cross-tenant link corruption.
    """
    affected = 0
    links = db.execute(
        select(StudyCaseDocument.case_id, StudyCaseDocument.checklist_key)
        .where(StudyCaseDocument.document_id == document.id)
        .order_by(StudyCaseDocument.case_id)
    ).all()
    for case_id, key in links:
        case = db.scalar(
            select(StudyCase)
            .where(
                StudyCase.id == case_id,
                StudyCase.user_id == document.user_id,
            )
            .with_for_update()
        )
        if case is None or key not in case.checklist:
            raise StudyDocumentIntegrityError(
                "Document association has an invalid owner or category"
            )
        checklist = dict(case.checklist)
        current = dict(checklist[key])
        if current.get("document_id") != document.id:
            continue
        replacement = db.scalar(
            select(StudyCaseDocument.document_id)
            .where(
                StudyCaseDocument.case_id == case_id,
                StudyCaseDocument.checklist_key == key,
                StudyCaseDocument.document_id != document.id,
            )
            .order_by(StudyCaseDocument.document_id)
            .limit(1)
        )
        current["document_id"] = replacement
        current["state"] = (
            "uploaded" if replacement is not None else "needs_verification"
        )
        checklist[key] = current
        case.checklist = checklist
        case.updated_at = utc_now_naive()
        affected += 1
    return affected
