from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image


USER_DATA = {
    "username": "imageocruser",
    "email": "imageocruser@example.com",
    "password": "TestPass123!",
}


def create_auth_headers(
    client: TestClient,
) -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json=USER_DATA,
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": USER_DATA["email"],
            "password": USER_DATA["password"],
        },
    )

    assert login_response.status_code == 200

    access_token = login_response.json()[
        "access_token"
    ]

    return {
        "Authorization": f"Bearer {access_token}",
    }


def create_png_bytes() -> bytes:
    buffer = BytesIO()

    image = Image.new(
        "RGB",
        (600, 200),
        "white",
    )

    image.save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def upload_test_image(
    client: TestClient,
    headers: dict[str, str],
):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "knowledge.png",
                create_png_bytes(),
                "image/png",
            ),
        },
    )


def test_authenticated_user_can_upload_image(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    response = upload_test_image(
        client,
        headers,
    )

    assert response.status_code == 201

    payload = response.json()

    assert (
        payload["original_filename"]
        == "knowledge.png"
    )
    assert payload["file_extension"] == ".png"
    assert payload["content_type"] == "image/png"
    assert payload["file_size"] > 0


def test_fake_png_is_rejected(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "fake.png",
                b"This is not a real image.",
                "image/png",
            ),
        },
    )

    assert response.status_code == 400


def test_image_can_be_processed_with_ocr(
    client: TestClient,
    monkeypatch,
) -> None:
    headers = create_auth_headers(client)

    upload_response = upload_test_image(
        client,
        headers,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    monkeypatch.setattr(
        (
            "app.parsers.image_parser."
            "pytesseract.image_to_string"
        ),
        lambda *args, **kwargs: (
            "Aqlyra retrieves private knowledge "
            "with grounded citations."
        ),
    )

    process_response = client.post(
        (
            "/api/v1/documents/"
            f"{document_id}/process"
        ),
        headers=headers,
    )

    assert process_response.status_code == 200

    process_payload = process_response.json()

    assert process_payload["status"] == "ready"
    assert process_payload["requires_ocr"] is True
    assert process_payload["word_count"] > 0

    units_response = client.get(
        (
            "/api/v1/documents/"
            f"{document_id}/units"
        ),
        headers=headers,
    )

    assert units_response.status_code == 200

    units_payload = units_response.json()

    combined_content = " ".join(
        item["content"]
        for item in units_payload["items"]
    )

    assert (
        "grounded citations"
        in combined_content
    )