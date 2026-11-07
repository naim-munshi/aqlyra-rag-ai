"""Owner-verifiable cloud photo into Converse (without private-data leakage)."""
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from PIL import Image

from app.llms.types import LLMGeneration
from app.services import chat_service, converse_vision_service


def test_cloud_image_chat_uses_verified_owned_temp_and_no_embeddings(tmp_path, monkeypatch):
    owner = str(uuid4())
    document = SimpleNamespace(
        id=str(uuid4()), user_id=owner, status="uploaded",
        storage_path=f"cloud://documents/{owner}/{uuid4()}.png",
        content_type="image/png", file_extension=".png",
    )
    db = Mock()
    db.scalar.return_value = document
    verified = tmp_path / "verified.png"
    Image.new("RGB", (2, 2)).save(verified)

    @contextmanager
    def owned_source(*, db, owner_id, document):
        assert owner_id == owner
        assert document.user_id == owner
        yield verified

    monkeypatch.setattr(chat_service, "cloud_processing_source", owned_source)
    monkeypatch.setattr(
        chat_service, "_prepare_normal_chat_generation",
        lambda **kwargs: (None, "Explain the uploaded photo"),
    )
    monkeypatch.setattr(
        chat_service, "_load_normal_attachment_context",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError(
            "Uploaded photo should not need embeddings or stored text chunks"
        )),
    )
    observed = []

    def fake_vision(**kwargs):
        observed.append(kwargs)
        return LLMGeneration(
            text="The photo is a small test image.", provider_name="groq",
            model_name="synthetic-test-model", response_id=None,
            input_tokens=None, output_tokens=None, total_tokens=None,
        )

    monkeypatch.setattr(chat_service, "generate_converse_image_reply", fake_vision)
    result = chat_service.generate_normal_document_chat_reply(
        db=db, conversation=SimpleNamespace(user_id=owner),
        message="Explain this photo", document_ids=(document.id,),
    )
    assert "small test image" in result.content
    assert len(observed) == 1
    assert observed[0]["verified_image_path"] == verified
    assert observed[0]["document"] is document


def test_converse_vision_reads_verified_cloud_image_not_local_path(tmp_path, monkeypatch):
    path = tmp_path / "verified.png"
    Image.new("RGB", (2, 2)).save(path)
    monkeypatch.setattr(converse_vision_service.settings, "GROQ_API_KEY", "synthetic-test-key")
    monkeypatch.setattr(converse_vision_service.settings, "CONVERSE_VISION_MODEL", "synthetic-model")
    monkeypatch.setattr(
        converse_vision_service, "resolve_stored_file_path",
        lambda *_: (_ for _ in ()).throw(AssertionError("Cloud key must never be treated as local")),
    )

    seen = []
    class FakeCompletions:
        def create(self, **kwargs):
            seen.append(kwargs)
            return SimpleNamespace(
                id="synthetic", model="synthetic-model",
                usage=None, choices=[SimpleNamespace(message=SimpleNamespace(content="An image."))],
            )
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())
    monkeypatch.setattr(converse_vision_service, "OpenAI", FakeOpenAI)

    document = SimpleNamespace(
        content_type="image/png",
        storage_path=f"cloud://documents/{uuid4()}/{uuid4()}.png",
    )
    result = converse_vision_service.generate_converse_image_reply(
        document=document, conversation_input="What is in this picture?",
        verified_image_path=path,
    )
    assert result.text == "An image."
    assert len(seen) == 1
    image_url = seen[0]["messages"][1]["content"][1]["image_url"]["url"]
    assert image_url.startswith("data:image/png;base64,")
    assert "cloud://" not in image_url
