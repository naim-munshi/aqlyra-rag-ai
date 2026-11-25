"""Prevent production image-provider failures being mislabeled as S3 errors."""
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from PIL import Image

from app.llms.types import LLMProviderRequestError
from app.services import cloud_process_io, converse_vision_service


def test_real_image_bound_keeps_original_unchanged_when_large():
    small = BytesIO()
    Image.new("RGB", (12, 8), "white").save(small, format="PNG")
    data = small.getvalue()
    # Large synthetic transport content, not a real user's image.
    padded = data + (b"\0" * (18 * 1024 * 1024))
    prepared, content_type = converse_vision_service._prepare_model_image(
        padded, "image/png",
    )
    assert content_type == "image/jpeg"
    assert len(prepared) < 18 * 1024 * 1024
    assert padded.startswith(data)


def test_cloud_source_preserves_llm_provider_error_after_verification(monkeypatch):
    img = BytesIO()
    Image.new("RGB", (2, 2), "white").save(img, format="PNG")
    image_data = img.getvalue()
    owner = str(uuid4())
    document = SimpleNamespace(
        user_id=owner, file_size=len(image_data),
        file_extension=".png",
        checksum_sha256=__import__("hashlib").sha256(image_data).hexdigest(),
    )
    class Body:
        def iter_chunks(self, chunk_size):
            yield image_data
        def close(self): pass

    class FakeS3:
        def get_object(self, **kwargs):
            return {"Body": Body(), "ContentLength": len(image_data)}

    monkeypatch.setattr(cloud_process_io, "verified_cloud_document_key", lambda **kwargs: "final/documents/test.png")
    monkeypatch.setattr(cloud_process_io.settings, "MAX_UPLOAD_SIZE_MB", 50)
    with pytest.raises(LLMProviderRequestError, match="vision provider error"):
        with cloud_process_io.cloud_processing_source(
            db=Mock(), owner_id=owner, document=document, store=FakeS3()
        ) as verified:
            assert verified.exists()
            raise LLMProviderRequestError("vision provider error")
