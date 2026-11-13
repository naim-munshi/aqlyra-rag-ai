"""Study Abroad checklist must never point at a moved or unlinked file.

Exercises actual API handlers and PostgreSQL-backed link rows using only
disposable CI accounts and document uploads; no external provider calls.
"""
from io import BytesIO
from uuid import uuid4

from app.api.dependencies import get_current_user
from app.main import app
from app.models.user import User

from test_study_abroad import authenticate, example_profile


def _owner(db):
    salt = uuid4().hex[:10]
    owner = User(
        email=f"study-move-{salt}@example.org",
        username=f"move_{salt}",
        hashed_password="ci-placeholder",
    )
    db.add(owner)
    db.commit()
    db.refresh(owner)
    return owner


def _ready_document(client, name: str, contents: bytes) -> str:
    uploaded = client.post(
        "/api/v1/documents/upload",
        files={"file": (name, BytesIO(contents), "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    document_id = uploaded.json()["id"]
    processed = client.post(f"/api/v1/documents/{document_id}/process")
    assert processed.status_code == 200, processed.text
    assert processed.json()["status"] == "ready"
    return document_id


def _checklist(client, case_id: str) -> dict:
    response = client.get(f"/api/v1/study-abroad/cases/{case_id}")
    assert response.status_code == 200, response.text
    return response.json()["checklist"]


def _link(client, case_id: str, document_id: str, key: str):
    response = client.post(
        f"/api/v1/study-abroad/cases/{case_id}/documents",
        json={"document_id": document_id, "checklist_key": key},
    )
    assert response.status_code == 201, response.text


def test_moved_link_rebinds_old_category_and_unlink_falls_back(client, db_session):
    owner = _owner(db_session)
    authenticate(owner)
    response = client.post("/api/v1/study-abroad/cases", json=example_profile())
    assert response.status_code == 201, response.text
    case_id = response.json()["id"]

    alpha = _ready_document(
        client, "transcript-a.txt", b"University transcript for document A."
    )
    beta = _ready_document(
        client, "language-b.txt", b"Independent proficiency record B."
    )

    _link(client, case_id, alpha, "academic")
    _link(client, case_id, beta, "academic")
    before = _checklist(client, case_id)
    assert before["academic"]["document_id"] == beta

    # Moving the NON-displayed link must keep the valid selected document.
    _link(client, case_id, alpha, "language")
    moved = _checklist(client, case_id)
    assert moved["academic"]["document_id"] == beta
    assert moved["academic"]["state"] == "uploaded"
    assert moved["language"]["document_id"] == alpha

    # Moving the displayed link must CLEAR the old category, not advertise
    # a document whose only database association moved elsewhere.
    _link(client, case_id, beta, "language")
    moved_again = _checklist(client, case_id)
    assert moved_again["academic"]["document_id"] is None
    assert moved_again["academic"]["state"] == "needs_verification"
    assert moved_again["language"]["document_id"] == beta

    rows = client.get(
        f"/api/v1/study-abroad/cases/{case_id}/documents"
    ).json()
    assert {(row["document_id"], row["checklist_key"]) for row in rows} == {
        (alpha, "language"), (beta, "language"),
    }

    # Removing the selected document should fall back to the other
    # matching document, and removing the last one clears its state.
    remove_beta = client.delete(
        f"/api/v1/study-abroad/cases/{case_id}/documents/{beta}"
    )
    assert remove_beta.status_code == 204
    fallback = _checklist(client, case_id)["language"]
    assert fallback["state"] == "uploaded"
    assert fallback["document_id"] == alpha

    remove_alpha = client.delete(
        f"/api/v1/study-abroad/cases/{case_id}/documents/{alpha}"
    )
    assert remove_alpha.status_code == 204
    empty = _checklist(client, case_id)["language"]
    assert empty["document_id"] is None
    assert empty["state"] == "needs_verification"
    assert client.get(
        f"/api/v1/study-abroad/cases/{case_id}/documents"
    ).json() == []

    # Unlink does not delete original documents owned by the applicant.
    for document_id in (alpha, beta):
        assert client.get(f"/api/v1/documents/{document_id}").status_code == 200


def test_foreign_owner_cannot_move_or_unlink_linked_study_files(client, db_session):
    owner, outsider = _owner(db_session), _owner(db_session)
    authenticate(owner)
    case = client.post(
        "/api/v1/study-abroad/cases", json=example_profile()
    ).json()
    document_id = _ready_document(
        client, "sensitive-transcript.txt", b"Owner only transcript."
    )
    _link(client, case["id"], document_id, "academic")
    authenticate(outsider)
    path = f"/api/v1/study-abroad/cases/{case['id']}/documents"
    assert client.post(
        path, json={"document_id": document_id, "checklist_key": "language"}
    ).status_code == 404
    assert client.delete(f"{path}/{document_id}").status_code == 404
    authenticate(owner)
    assert _checklist(client, case["id"])["academic"]["document_id"] == document_id
