"""Optional synthetic Groq vision provider smoke. Never reads a user object."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace

from PIL import Image

from app.services.converse_vision_service import generate_converse_image_reply


def verify_vision_provider() -> None:
    with TemporaryDirectory(prefix="aqlyra-vision-probe-") as directory:
        image_path = Path(directory) / "synthetic.png"
        Image.new("RGB", (2, 2), (255, 255, 255)).save(image_path)
        document = SimpleNamespace(
            content_type="image/png",
            storage_path="synthetic://probe-do-not-read",
        )
        generation = generate_converse_image_reply(
            document=document,
            conversation_input="Reply with one short sentence confirming you can see this synthetic white image.",
            verified_image_path=image_path,
        )
        if not generation.text.strip():
            raise RuntimeError("Vision provider returned no answer")


if __name__ == "__main__":
    try:
        verify_vision_provider()
        print("VISION_MODEL_PROBE=PASS", flush=True)
    except Exception:
        print("VISION_MODEL_PROBE=FAIL", flush=True)
        raise SystemExit(1)
