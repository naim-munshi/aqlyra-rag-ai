"""End-to-end artifacts authorization, real bytes, and formula safety."""
from io import BytesIO
from types import SimpleNamespace

from docx import Document
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from pptx import Presentation

from app.services.artifact_rendering import render_artifact


def _auth(client: TestClient, username: str) -> dict[str, str]:
    email = username + "@example.com"
    assert client.post("/api/v1/auth/register", json={
        "username": username, "email": email, "password": "SecurePass123!",
    }).status_code == 201
    token_response = client.post("/api/v1/auth/login", json={
        "email": email, "password": "SecurePass123!",
    })
    assert token_response.status_code == 200
    return {"Authorization": "Bearer " + token_response.json()["access_token"]}


def test_all_formats_render_real_files():
    markdown = (
        "# RAG Research\n\n## Results\n"
        "| Year | Cost |\n| --- | --- |\n| 2026 | 350 |\n"
        "| 2027 | =HYPERLINK(1) |\n"
        "## Conclusion\n- Citation validated\n- Private workspace\n"
    )
    assert render_artifact(markdown, "md").startswith(b"# RAG")
    docx = Document(BytesIO(render_artifact(markdown, "docx")))
    assert any("RAG Research" in p.text for p in docx.paragraphs)
    xlsx = load_workbook(BytesIO(render_artifact(markdown, "xlsx")), data_only=False)
    assert xlsx.active["B5"].data_type == "s"
    assert xlsx.active["B5"].value.startswith("'=HYPERLINK")
    slides = Presentation(BytesIO(render_artifact(markdown, "pptx")))
    assert len(slides.slides) >= 2
    assert render_artifact(markdown, "pdf").startswith(b"%PDF")
    for kind in ["xlsx", "pptx", "docx"]:
        assert render_artifact(markdown, kind).startswith(b"PK")


def test_artifacts_auth_owner_scope_versions_and_download(client: TestClient):
    url = "/api/v1/artifacts"
    assert client.get(url).status_code == 401
    assert client.post(url + "/render", json={
        "title": "Report", "format": "md", "content": "# Secure",
    }).status_code == 401
    alpha = _auth(client, "artifactalpha")
    beta = _auth(client, "artifactbeta")
    response = client.post(url + "/render", headers=alpha, json={
        "title": "Report", "format": "md", "content": "# Secure report",
    })
    assert response.status_code == 201
    item = response.json()
    assert item["filename"].endswith(".md")
    assert item["content"] == "# Secure report"
    artifact_id = item["id"]
    assert client.get(url, headers=alpha).json()["total"] == 1
    assert client.get(url, headers=beta).json()["total"] == 0
    assert client.get(url + "/" + artifact_id, headers=beta).status_code == 404
    assert client.get(url + "/" + artifact_id + "/download", headers=beta).status_code == 404
    assert client.delete(url + "/" + artifact_id, headers=beta).status_code == 404
    download = client.get(url + "/" + artifact_id + "/download", headers=alpha)
    assert download.status_code == 200
    assert download.content == b"# Secure report"
    assert download.headers["cache-control"] == "private, no-store"
    assert "attachment" in download.headers["content-disposition"]
    assert client.delete(url + "/" + artifact_id, headers=alpha).status_code == 204
    assert client.get(url + "/" + artifact_id, headers=alpha).status_code == 404


def test_deterministic_local_mode_fails_closed(client: TestClient):
    alpha = _auth(client, "artifactlocal")
    response = client.post("/api/v1/artifacts/generate", headers=alpha, json={
        "title": "Draft", "format": "pptx",
        "prompt": "Write a professional presentation about RAG.",
    })
    assert response.status_code == 503
    assert client.get("/api/v1/artifacts", headers=alpha).json()["total"] == 0


def test_real_provider_output_generates_docx(client: TestClient, monkeypatch):
    alpha = _auth(client, "artifactwriter")
    class Provider:
        def generate(self, **kwargs):
            assert "Write a research report" in kwargs["input_text"]
            return SimpleNamespace(
                text="# Research\n\n## Findings\n- Real content generated",
                provider_name="test-provider",
            )
    monkeypatch.setattr(
        "app.api.artifacts.settings.LLM_PROVIDER", "openai",
    )
    monkeypatch.setattr(
        "app.api.artifacts.create_configured_llm_provider",
        lambda: Provider(),
    )
    response = client.post("/api/v1/artifacts/generate", headers=alpha, json={
        "title": "Research", "format": "docx",
        "prompt": "Write a research report about systems and AI.",
    })
    assert response.status_code == 201
    item = response.json()
    assert item["provider_name"] == "test-provider"
    data = client.get(
        "/api/v1/artifacts/" + item["id"] + "/download", headers=alpha,
    )
    assert data.status_code == 200
    doc = Document(BytesIO(data.content))
    assert any("Real content generated" in p.text for p in doc.paragraphs)


def test_no_external_users_document_leak(client: TestClient):
    url = "/api/v1/artifacts/generate"
    alpha = _auth(client, "artifactowner")
    beta = _auth(client, "artifactother")
    uploaded = client.post("/api/v1/documents/upload", headers=alpha, files={
        "file": ("secret.md", b"# Private source document", "text/markdown"),
    })
    assert uploaded.status_code == 201
    document_id = uploaded.json()["id"]
    result = client.post(url, headers=beta, json={
        "title": "Attempt", "format": "docx",
        "prompt": "Generate report from another user document.",
        "document_ids": [document_id],
        "confirm_share_documents": True,
    })
    assert result.status_code == 422
    assert client.get("/api/v1/artifacts", headers=beta).json()["total"] == 0


def test_bad_identifiers_not_usable(client: TestClient):
    alpha = _auth(client, "artifactpath")
    assert client.get(
        "/api/v1/artifacts/../../etc/passwd", headers=alpha,
        follow_redirects=False,
    ).status_code in (404, 405)
    assert client.get(
        "/api/v1/artifacts/not-a-uuid", headers=alpha,
    ).status_code == 404


def test_grounded_artifact_reuses_scoped_rag_and_citations(
    client: TestClient, db_session, monkeypatch,
):
    from sqlalchemy import select
    from app.models.document import Document

    owner = _auth(client, "artifactgrounded")
    uploaded = client.post("/api/v1/documents/upload", headers=owner, files={
        "file": ("my-source.md", b"# Private evidence\nRAG content.", "text/markdown"),
    })
    assert uploaded.status_code == 201
    doc_id = uploaded.json()["id"]
    document = db_session.scalar(select(Document).where(Document.id == doc_id))
    document.status = "ready"
    db_session.commit()
    calls = []

    def fake_answer_question(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            is_refusal=False,
            citations=(SimpleNamespace(
                source_id="S1", original_filename="my-source.md",
                start_page=1, document_id=doc_id,
            ),),
            answer_text="## Verified evidence\nA fact supported by [S1].",
            provider_name="test-rag",
            citation_count=1,
        )

    monkeypatch.setattr("app.api.artifacts.answer_question", fake_answer_question)
    no_consent = client.post("/api/v1/artifacts/generate", headers=owner, json={
        "title": "Grounded", "format": "md",
        "prompt": "Summarize the private evidence from my documents.",
        "document_ids": [doc_id],
    })
    assert no_consent.status_code == 422
    assert len(calls) == 0

    response = client.post("/api/v1/artifacts/generate", headers=owner, json={
        "title": "Grounded", "format": "md",
        "prompt": "Summarize the private evidence from my documents.",
        "document_ids": [doc_id],
        "confirm_share_documents": True,
    })
    assert response.status_code == 201
    data = response.json()
    assert data["citation_count"] == 1
    assert data["source_document_ids"] == [doc_id]
    assert "[S1]" in data["content"]
    assert "## Source references" in data["content"]
    assert "my-source.md" in data["content"]
    assert doc_id in data["content"]
    assert len(calls) == 1
    assert calls[0]["document_ids"] == (doc_id,)
    assert calls[0]["user_id"] == document.user_id


def test_renderer_never_silently_truncates_source_or_slides():
    import pytest
    from app.services.artifact_rendering import render_artifact

    with pytest.raises(ValueError, match="450 source lines"):
        render_artifact("# Long\n" + ("short\n" * 451), "docx")
    with pytest.raises(ValueError, match="12 columns"):
        render_artifact("| " + " | ".join(str(x) for x in range(13)) + " |", "xlsx")
    with pytest.raises(ValueError, match="25 slides"):
        parts = ["# Title"]
        for index in range(30):
            parts.extend([f"## Section {index}", "- Point"])
        render_artifact("\n".join(parts), "pptx")


def test_artifact_storage_quota_is_atomic(tmp_path, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from uuid import uuid4
    from app.services import artifact_storage
    from app.config.settings import settings

    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(artifact_storage, "MAX_ARTIFACTS_PER_USER", 2)
    owner = str(uuid4())

    def attempt(index):
        try:
            artifact_storage.create_artifact(
                user_id=owner, title=f"Concurrent {index}",
                kind="md", content="# Test\nUntrusted content",
                provider_name="test", source_document_ids=[],
                citation_count=0,
            )
            return True
        except artifact_storage.ArtifactQuotaError:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(attempt, range(12)))
    assert results.count(True) == 2
    assert results.count(False) == 10
    assert len(artifact_storage.list_artifacts(user_id=owner)) == 2


def test_private_neon_object_artifacts_are_owner_scoped_and_cleaned(tmp_path, monkeypatch):
    import json
    from io import BytesIO
    from uuid import uuid4

    from app.config.settings import settings
    from app.services import artifact_storage

    class FakeS3:
        def __init__(self):
            self.objects = {}

        def put_object(self, *, Bucket, Key, Body, ContentType, CacheControl):
            self.objects[(Bucket, Key)] = (
                Body if isinstance(Body, bytes) else Body.read(),
                ContentType,
            )

        def get_object(self, *, Bucket, Key):
            if (Bucket, Key) not in self.objects:
                error = RuntimeError("missing synthetic object")
                error.response = {
                    "Error": {"Code": "NoSuchKey"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                }
                raise error
            body, _ = self.objects[(Bucket, Key)]
            return {"Body": BytesIO(body), "ContentLength": len(body)}

        def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
            keys = sorted(
                key for bucket, key in self.objects
                if bucket == Bucket and key.startswith(Prefix)
            )[:MaxKeys]
            return {
                "Contents": [{"Key": key} for key in keys],
                "IsTruncated": False,
            }

        def delete_object(self, *, Bucket, Key):
            self.objects.pop((Bucket, Key), None)

    owner = str(uuid4())
    other_user = str(uuid4())
    fake = FakeS3()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AWS_ENDPOINT_URL_S3", "https://test.aws.neon.tech")
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(settings, "AWS_REGION", "us-east-2")
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "aqlyra-private-test")
    monkeypatch.setattr(settings, "LOCAL_UPLOAD_DURABLE_STORAGE_VERIFIED", False)
    monkeypatch.setattr(settings, "EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED", False)
    monkeypatch.setattr(artifact_storage, "_s3_client", lambda: fake)

    item = artifact_storage.create_artifact(
        user_id=owner, title="Private report", kind="md",
        content="# Private report\n\nNever expose this to another account.",
        provider_name="synthetic-test", source_document_ids=[], citation_count=0,
    )
    assert item["owner_id"] == owner
    assert item["sha256"]
    assert artifact_storage.read_artifact(
        user_id=owner, artifact_id=item["id"]
    )["content"].startswith("# Private report")
    assert artifact_storage.read_artifact(
        user_id=other_user, artifact_id=item["id"]
    ) is None
    assert artifact_storage.list_artifacts(user_id=other_user) == []
    assert len(artifact_storage.list_artifacts(user_id=owner)) == 1
    assert all(
        key.startswith(f"artifacts/{owner}/")
        for bucket, key in fake.objects
    )
    assert artifact_storage.delete_artifact(
        user_id=other_user, artifact_id=item["id"]
    ) is False

    downloaded = artifact_storage.artifact_download(
        user_id=owner, artifact_id=item["id"]
    )
    assert downloaded is not None
    path, metadata = downloaded
    assert path.read_bytes() == b"# Private report\n\nNever expose this to another account."
    assert metadata["sha256"] == item["sha256"]
    artifact_storage.cleanup_artifact_download(path)
    assert not path.exists()

    assert artifact_storage.delete_artifact(
        user_id=owner, artifact_id=item["id"]
    ) is True
    assert artifact_storage.read_artifact(
        user_id=owner, artifact_id=item["id"]
    ) is None
    assert fake.objects == {}


def test_private_object_artifact_quota_and_provider_failure_fail_closed(monkeypatch):
    from uuid import uuid4

    from app.config.settings import settings
    from app.services import artifact_storage

    class FakeS3:
        def __init__(self):
            self.objects = {}

        def put_object(self, *, Bucket, Key, Body, ContentType, CacheControl):
            self.objects[(Bucket, Key)] = (
                Body if isinstance(Body, bytes) else Body.read(), ContentType
            )

        def list_objects_v2(self, *, Bucket, Prefix, MaxKeys):
            keys = sorted(
                key for bucket, key in self.objects
                if bucket == Bucket and key.startswith(Prefix)
            )[:MaxKeys]
            return {"Contents": [{"Key": key} for key in keys], "IsTruncated": False}

        def delete_object(self, *, Bucket, Key):
            self.objects.pop((Bucket, Key), None)

        def get_object(self, *, Bucket, Key):
            raise AssertionError("This quota test should not need to read objects")

    owner = str(uuid4())
    fake = FakeS3()
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "PRIVATE_OBJECT_STORAGE_ENABLED", True)
    monkeypatch.setattr(settings, "AWS_ENDPOINT_URL_S3", "https://test.aws.neon.tech")
    monkeypatch.setattr(settings, "AWS_ACCESS_KEY_ID", "test-access")
    monkeypatch.setattr(settings, "AWS_SECRET_ACCESS_KEY", "test-secret")
    monkeypatch.setattr(settings, "AWS_REGION", "us-east-2")
    monkeypatch.setattr(settings, "OBJECT_STORAGE_BUCKET", "aqlyra-private-test")
    monkeypatch.setattr(settings, "EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED", False)
    monkeypatch.setattr(settings, "UPLOAD_DIR", tmp_path if "tmp_path" in globals() else settings.UPLOAD_DIR)
    monkeypatch.setattr(artifact_storage, "MAX_ARTIFACTS_PER_USER", 1)
    monkeypatch.setattr(artifact_storage, "_s3_client", lambda: fake)

    artifact_storage.create_artifact(
        user_id=owner, title="One", kind="md", content="# One",
        provider_name="test", source_document_ids=[], citation_count=0,
    )
    with pytest.raises(artifact_storage.ArtifactQuotaError):
        artifact_storage.create_artifact(
            user_id=owner, title="Two", kind="md", content="# Two",
            provider_name="test", source_document_ids=[], citation_count=0,
        )

    class BrokenS3:
        def list_objects_v2(self, **kwargs):
            return {"Contents": [], "IsTruncated": False}

        def put_object(self, **kwargs):
            raise RuntimeError("provider error must not escape")

        def delete_object(self, **kwargs):
            pass

    monkeypatch.setattr(artifact_storage, "_s3_client", lambda: BrokenS3())
    # Even with the old ephemeral test switch set, an explicitly configured
    # private provider failure must not fall back to an ephemeral disk.
    monkeypatch.setattr(settings, "EPHEMERAL_ARTIFACT_TEST_MODE_ENABLED", True)
    with pytest.raises(artifact_storage.ArtifactStorageError, match="Private artifact write failed"):
        artifact_storage.create_artifact(
            user_id=str(uuid4()), title="No fallback", kind="md", content="# No fallback",
            provider_name="test", source_document_ids=[], citation_count=0,
        )
