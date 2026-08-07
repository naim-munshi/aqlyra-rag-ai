from fastapi.testclient import TestClient


USER_DATA = {
    "username": "processinguser",
    "email": "processinguser@example.com",
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

    token = login_response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
    }


def upload_test_document(
    client: TestClient,
    headers: dict[str, str],
):
    content = (
        "# Introduction\n\n"
        "Aqlyra RAG AI securely processes documents.\n\n"
        "# Retrieval\n\n"
        "Relevant evidence is retrieved with citations.\n"
    ).encode("utf-8")

    return client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "processing-test.md",
                content,
                "text/markdown",
            ),
        },
    )


def test_document_can_be_processed(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    upload_response = upload_test_document(
        client=client,
        headers=headers,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    process_response = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=headers,
    )

    assert process_response.status_code == 200

    payload = process_response.json()

    assert payload["id"] == document_id
    assert payload["status"] == "ready"
    assert payload["word_count"] > 0
    assert payload["requires_ocr"] is False
    assert payload["processed_at"] is not None


def test_processed_document_has_units(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    upload_response = upload_test_document(
        client=client,
        headers=headers,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    process_response = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=headers,
    )

    assert process_response.status_code == 200

    units_response = client.get(
        f"/api/v1/documents/{document_id}/units",
        headers=headers,
    )

    assert units_response.status_code == 200

    payload = units_response.json()

    assert payload["document_id"] == document_id
    assert payload["document_status"] == "ready"
    assert payload["total"] >= 2
    assert len(payload["items"]) >= 2

    combined_content = " ".join(
        unit["content"]
        for unit in payload["items"]
    )

    assert "securely processes documents" in combined_content
    assert "retrieved with citations" in combined_content


def test_ready_document_cannot_be_processed_again(
    client: TestClient,
) -> None:
    headers = create_auth_headers(client)

    upload_response = upload_test_document(
        client=client,
        headers=headers,
    )

    assert upload_response.status_code == 201

    document_id = upload_response.json()["id"]

    first_process_response = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=headers,
    )

    second_process_response = client.post(
        f"/api/v1/documents/{document_id}/process",
        headers=headers,
    )

    assert first_process_response.status_code == 200
    assert second_process_response.status_code == 409
