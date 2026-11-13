"""Never expose QA answer sheets as user knowledge or cite them as sources.

The owner still retains the original document and can remove it through
the ordinary authenticated cloud deletion workflow. No data is deleted here.
"""
from app.models.document import Document

QUARANTINED_SOURCE_FILENAMES = (
    "Aqlyra_RAG_Expected_Answers_DO_NOT_UPLOAD.md",
)


def permitted_retrieval_document():
    return Document.original_filename.not_in(QUARANTINED_SOURCE_FILENAMES)
