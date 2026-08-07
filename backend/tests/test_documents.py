from fastapi.testclient import TestClient


USER_DATA = {
    "username": "documentuser",
    "email": "documentuser@example.com",
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


def upload_markdown_document(
    client: TestClient,
    headers: dict[str, str],
):
    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "rag-test.md",
                (
                    "# Aqlyra RAG AI\n\n"
                    "This document explains secure "
                    "retrieval-augmented generation."
                ).encode("utf-8"),
                "text/markdown",
            ),
        },
    )


def test_document_upload_requires_authentication(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/v1/documents/upload",
        files={
            "file": (
                "unauthorized.md",
                b"# Unauthorized upload",
                "text/markdown",
            ),
        },
    )

    assert response.status_code == 401


def test_authenticated_user_can_upload_document(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    response = upload_markdown_document(
        client=client,
        headers=headers,
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["original_filename"] == "rag-test.md"
    assert payload["file_extension"] == ".md"
    assert payload["status"] == "uploaded"
    assert payload["file_size"] > 0
    assert payload["checksum_sha256"]
    assert payload["requires_ocr"] is False


def test_duplicate_document_returns_conflict(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    first_response = upload_markdown_document(
        client=client,
        headers=headers,
    )

    second_response = upload_markdown_document(
        client=client,
        headers=headers,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409

    first_document_id = first_response.json()["id"]
    error_detail = second_response.json()["detail"]

    assert error_detail["message"] == (
        "This document has already been uploaded"
    )

    assert error_detail["document_id"] == (
        first_document_id
    )


def test_user_can_list_read_and_delete_document(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    upload_response = upload_markdown_document(
        client=client,
        headers=headers,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    list_response = client.get(
        "/api/v1/documents",
        headers=headers,
    )

    assert list_response.status_code == 200

    list_payload = list_response.json()

    assert list_payload["total"] == 1
    assert list_payload["items"][0]["id"] == document_id

    read_response = client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )

    assert read_response.status_code == 200
    assert read_response.json()["id"] == document_id

    delete_response = client.delete(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )

    assert delete_response.status_code == 204

    deleted_read_response = client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )

    assert deleted_read_response.status_code == 404
