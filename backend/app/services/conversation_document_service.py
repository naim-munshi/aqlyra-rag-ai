from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.conversation import Conversation
from app.models.conversation_document import (
    ConversationDocument,
)
from app.models.document import Document


MAX_CONVERSATION_DOCUMENTS = 50


class ConversationDocumentScopeError(
    ValueError
):
    pass


@dataclass(
    frozen=True,
    slots=True,
)
class ConversationDocumentScope:
    effective_document_ids: tuple[str, ...]
    new_document_ids: tuple[str, ...]


def list_conversation_document_ids(
    *,
    db: Session,
    conversation_id: str,
) -> tuple[str, ...]:
    statement = (
        select(
            ConversationDocument.document_id
        )
        .where(
            ConversationDocument.conversation_id
            == conversation_id
        )
        .order_by(
            ConversationDocument.created_at.asc(),
            ConversationDocument.document_id.asc(),
        )
    )

    return tuple(
        db.scalars(statement).all()
    )


def resolve_conversation_document_scope(
    *,
    db: Session,
    conversation: Conversation,
    requested_document_ids: tuple[str, ...],
) -> ConversationDocumentScope:
    if conversation.mode == "normal":
        # Normal-chat attachments are valid only for
        # the current turn. They are never persisted
        # into conversation_documents.
        effective_document_ids = (
            requested_document_ids
        )
        new_document_ids = ()

    elif conversation.mode == "knowledge":
        existing_document_ids = (
            list_conversation_document_ids(
                db=db,
                conversation_id=conversation.id,
            )
        )

        existing_set = set(
            existing_document_ids
        )

        new_document_ids = tuple(
            document_id
            for document_id
            in requested_document_ids
            if document_id not in existing_set
        )

        effective_document_ids = (
            existing_document_ids
            + new_document_ids
        )

    else:
        raise ConversationDocumentScopeError(
            "Unsupported conversation mode"
        )

    if (
        len(effective_document_ids)
        > MAX_CONVERSATION_DOCUMENTS
    ):
        raise ConversationDocumentScopeError(
            "A knowledge conversation can "
            "reference at most 50 documents"
        )

    if not effective_document_ids:
        return ConversationDocumentScope(
            effective_document_ids=(),
            new_document_ids=(),
        )

    rows = db.execute(
        select(
            Document.id,
            Document.user_id,
            Document.status,
        ).where(
            Document.id.in_(
                effective_document_ids
            )
        )
    ).all()

    documents = {
        row.id: row
        for row in rows
    }

    missing = [
        document_id
        for document_id
        in effective_document_ids
        if document_id not in documents
    ]

    if missing:
        raise ConversationDocumentScopeError(
            "One or more selected documents "
            "are not available"
        )

    wrong_owner = [
        document_id
        for document_id
        in effective_document_ids
        if (
            documents[document_id].user_id
            != conversation.user_id
        )
    ]

    if wrong_owner:
        raise ConversationDocumentScopeError(
            "One or more selected documents "
            "are not available"
        )

    not_ready = [
        document_id
        for document_id
        in effective_document_ids
        if (
            documents[document_id].status
            != "ready"
        )
    ]

    if not_ready:
        raise ConversationDocumentScopeError(
            "Selected documents must be "
            "processed and ready"
        )

    return ConversationDocumentScope(
        effective_document_ids=(
            effective_document_ids
        ),
        new_document_ids=(
            new_document_ids
        ),
    )
