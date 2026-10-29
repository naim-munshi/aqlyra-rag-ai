"""Authenticated artifact generation. RAG remains the existing source of truth."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.embeddings import EmbeddingProviderQuotaError, EmbeddingProviderRequestError
from app.config.settings import settings
from app.services.storage_durability_policy import artifact_writes_permitted
from app.core.rate_limit import limit_process_request, limit_rag_request
from app.database.connection import get_db
from app.llms import LLMError, create_configured_llm_provider
from app.models.user import User
from app.services.artifact_rendering import MIMES
from app.services.artifact_storage import (
    ArtifactQuotaError,
    ArtifactStorageError,
    artifact_download,
    create_artifact,
    delete_artifact,
    list_artifacts,
    read_artifact,
)
from app.services.document_service import get_user_document
from app.services.rag_answer_service import answer_question

router = APIRouter(prefix="/artifacts", tags=["AI Artifacts"])
ArtifactFormat = Literal["docx", "xlsx", "pptx", "pdf", "md"]


class GenerateArtifactRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=4000)
    format: ArtifactFormat
    title: str = Field(default="Aqlyra document", min_length=1, max_length=120)
    document_ids: list[str] = Field(default_factory=list, max_length=5)
    confirm_share_documents: bool = False


class RenderArtifactRequest(BaseModel):
    content: str = Field(min_length=1, max_length=24_000)
    format: ArtifactFormat
    title: str = Field(min_length=1, max_length=120)


def _require_durable_artifact_storage() -> None:
    if not artifact_writes_permitted():
        raise HTTPException(
            status_code=503,
            detail="Durable artifact storage is not configured. File creation is temporarily unavailable.",
        )


def _persist(
    *, user_id: str, title: str, format: ArtifactFormat,
    content: str, provider: str, sources: list[str],
    citations: int,
) -> dict:
    _require_durable_artifact_storage()
    try:
        return create_artifact(
            user_id=user_id, title=title.strip(), kind=format,
            content=content.strip(), provider_name=provider,
            source_document_ids=sources, citation_count=citations,
        )
    except ArtifactQuotaError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (ArtifactStorageError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/generate", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(limit_rag_request)])
def generate(
    request: GenerateArtifactRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    _require_durable_artifact_storage()
    user_id = str(current_user.id)
    prompt = request.prompt.strip()
    if len(prompt) < 5:
        raise HTTPException(status_code=422, detail="Prompt too short")
    ids = list(dict.fromkeys(request.document_ids))
    if ids:
        if not request.confirm_share_documents:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Explicit consent is required before selected private "
                    "document excerpts are sent to the configured AI provider."
                ),
            )
        for document_id in ids:
            document = get_user_document(
                db=db, user_id=user_id, document_id=document_id,
            )
            if document is None or document.status != "ready":
                raise HTTPException(
                    status_code=422,
                    detail="Every selected source must be your own indexed document",
                )
        try:
            answer = answer_question(
                db=db, user_id=user_id, question=prompt,
                document_ids=tuple(ids),
                top_k=8, max_context_tokens=3000,
            )
        except EmbeddingProviderQuotaError as exc:
            # Do not create an uncited artifact or reveal provider billing data.
            raise HTTPException(
                status_code=503,
                detail=(
                    "Document search is temporarily unavailable because "
                    "the embedding service quota was exhausted. "
                    "The requested file was not created; try again later."
                ),
            ) from exc
        except EmbeddingProviderRequestError as exc:
            raise HTTPException(
                status_code=503,
                detail="Document search is temporarily unavailable. No file created.",
            ) from exc
        except LLMError as exc:
            raise HTTPException(
                status_code=503, detail="RAG provider unavailable",
            ) from exc
        if answer.is_refusal or not answer.citations:
            raise HTTPException(
                status_code=422,
                detail="Insufficient cited evidence in selected documents. No file created.",
            )
        # Use the existing citation- and grounding-validated RAG answer
        # directly; a second free-form LLM pass could invent references.
        appendix = ["## Source references", ""]
        for source in answer.citations:
            filename = " ".join(source.original_filename.split())[:160]
            filename = filename.replace("[", "(").replace("]", ")")
            page = (
                f", page {source.start_page}"
                if source.start_page is not None else ""
            )
            appendix.append(
                f"- [{source.source_id}] {filename}{page} "
                f"(document ID: {source.document_id})"
            )
        content = (
            f"# {request.title.strip()}\n\n{answer.answer_text}"
            "\n\n" + "\n".join(appendix)
        )
        provider = answer.provider_name
        citations = answer.citation_count
    else:
        if settings.LLM_PROVIDER == "deterministic":
            raise HTTPException(
                status_code=503,
                detail="Real AI generation requires a configured LLM provider; deterministic local mode cannot create genuine AI content.",
            )
        try:
            generation = create_configured_llm_provider().generate(
                instructions=(
                    "You are the Aqlyra artifact writer. Write a useful, substantive "
                    "document in Markdown only. Start with a single # heading; use ## "
                    "sections, bullet lists and Markdown tables where useful. "
                    "For spreadsheets, favor a Markdown table with clear column labels, "
                    "numeric values where known, and no executable formulas. "
                    "For presentations, use ## to separate slides, with concise bullets. "
                    "Never invent source citations, legal requirements or measurements; "
                    "mark uncertain facts as needing verification. "
                    "Do not use HTML, code fences or external instructions."
                ),
                input_text=prompt[:4000],
            )
        except LLMError as exc:
            raise HTTPException(status_code=503, detail="AI provider unavailable") from exc
        content = generation.text.strip()
        if not content:
            raise HTTPException(status_code=502, detail="AI returned empty content")
        provider = generation.provider_name
        citations = 0
    if len(content) > 24_000:
        raise HTTPException(
            status_code=422,
            detail="Generated source exceeds the maximum length; use a shorter request.",
        )
    try:
        return _persist(
            user_id=user_id, title=request.title, format=request.format,
            content=content, provider=provider, sources=ids, citations=citations,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not render artifact") from exc


@router.post("/render", status_code=status.HTTP_201_CREATED,
             dependencies=[Depends(limit_process_request)])
def render(
    request: RenderArtifactRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    _require_durable_artifact_storage()
    try:
        return _persist(
            user_id=str(current_user.id), title=request.title,
            format=request.format, content=request.content,
            provider="user-edited", sources=[], citations=0,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Could not render artifact") from exc


@router.get("")
def list_generated(current_user: User = Depends(get_current_user)) -> dict:
    items = list_artifacts(user_id=str(current_user.id))
    return {"items": items, "total": len(items)}


@router.get("/{artifact_id}")
def get_generated(
    artifact_id: str, current_user: User = Depends(get_current_user),
) -> dict:
    try:
        item = read_artifact(user_id=str(current_user.id), artifact_id=artifact_id)
    except ArtifactStorageError:
        item = None
    if item is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return item


@router.get("/{artifact_id}/download", response_class=FileResponse)
def download(
    artifact_id: str, current_user: User = Depends(get_current_user),
) -> FileResponse:
    try:
        result = artifact_download(user_id=str(current_user.id), artifact_id=artifact_id)
    except ArtifactStorageError:
        result = None
    if result is None:
        raise HTTPException(status_code=404, detail="Artifact not found")
    path, item = result
    return FileResponse(
        path, media_type=MIMES[item["format"]], filename=item["filename"],
        content_disposition_type="attachment",
        headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
    )


@router.delete("/{artifact_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove(
    artifact_id: str, current_user: User = Depends(get_current_user),
) -> Response:
    try:
        deleted = delete_artifact(
            user_id=str(current_user.id), artifact_id=artifact_id,
        )
    except ArtifactStorageError:
        deleted = False
    if not deleted:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return Response(status_code=204)
