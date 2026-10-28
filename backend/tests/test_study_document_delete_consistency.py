"""Cross-feature deletion: source RAG documents must not leave stale case IDs.

All accounts, PostgreSQL rows and private S3 bytes are disposable CI fixtures.
"""
from app.config.settings import settings
from app.core.datetime_utils import utc_now_naive
from app.models.document import Document
from app.services.cloud_document_finalization import finalize_cloud_upload
from test_cloud_document_finalization import InMemoryS3, configured, reserve
from test_study_abroad import authenticate, example_profile
from test_study_abroad_checklist_rebinding import (
    _checklist,
    _link,
    _owner,
    _ready_document,
)


def _case(client):
    response = client.post(
        "/api/v1/study-abroad/cases", json=example_profile()
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_local_document_delete_repairs_study_checklist_and_fallback(
    client, db_session,
):
    owner = _owner(db_session)
    authenticate(owner)
    case_id = _case(client)
    first = _ready_document(
        client, "academic-one.txt", b"First student's academic record."
    )
    second = _ready_document(
        client, "academic-two.txt", b"Second student's academic record."
    )
    _link(client, case_id, first, "academic")
    _link(client, case_id, second, "academic")
    assert _checklist(client, case_id)["academic"]["document_id"] == second

    # Delete through the ordinary Documents API, NOT the Study Abroad API.
    assert client.delete(f"/api/v1/documents/{second}").status_code == 204
    after = _checklist(client, case_id)["academic"]
    assert after["document_id"] == first
    assert after["state"] == "uploaded"
    associations = client.get(
        f"/api/v1/study-abroad/cases/{case_id}/documents"
    ).json()
    assert [(row["document_id"], row["checklist_key"]) for row in associations] == [
        (first, "academic")
    ]
    assert client.delete(f"/api/v1/documents/{first}").status_code == 204
    last = _checklist(client, case_id)["academic"]
    assert last["document_id"] is None
    assert last["state"] == "needs_verification"
    assert client.get(
        f"/api/v1/study-abroad/cases/{case_id}/documents"
    ).json() == []


def test_cloud_document_delete_repairs_study_checklist_and_respects_owner(
    client, db_session, monkeypatch,
):
    from app.services import cloud_document_deletion

    owner = _owner(db_session)
    owner.email_verified_at = utc_now_naive()
    db_session.commit()
    authenticate(owner)
    case_id = _case(client)
    store = InMemoryS3(b"Private cloud academic record for a student.")
    grant = reserve(db_session, owner, store)
    result = finalize_cloud_upload(
        db=db_session, owner=owner, intent_id=grant.intent_id,
        cfg=configured(), client=store,
    )
    document = db_session.get(Document, result.document_id)
    assert document is not None
    document.status = "ready"
    db_session.commit()
    _link(client, case_id, result.document_id, "academic")

    other = _owner(db_session)
    authenticate(other)
    assert client.delete(
        f"/api/v1/documents/{result.document_id}"
    ).status_code == 404

    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "private-documents")
    monkeypatch.setattr(cloud_document_deletion, "_client", lambda cfg: store)
    authenticate(owner)
    assert client.delete(
        f"/api/v1/documents/{result.document_id}"
    ).status_code == 204
    assert result.final_object_key not in store.objects
    item = _checklist(client, case_id)["academic"]
    assert item["document_id"] is None
    assert item["state"] == "needs_verification"
    assert client.get(
        f"/api/v1/study-abroad/cases/{case_id}/documents"
    ).json() == []
