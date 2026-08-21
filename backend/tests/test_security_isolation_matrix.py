from fastapi.testclient import TestClient


PASSWORD = "SecurityTestPass123!"


def create_auth_headers(
    client: TestClient,
    *,
    suffix: str,
) -> dict[str, str]:
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": suffix,
            "email": f"{suffix}@example.com",
            "password": PASSWORD,
        },
    )

    assert register_response.status_code == 201

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "email": f"{suffix}@example.com",
            "password": PASSWORD,
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()[
        "access_token"
    ]

    return {
        "Authorization": f"Bearer {token}",
    }


def upload_private_document(
    client: TestClient,
    headers: dict[str, str],
) -> tuple[str, bytes]:
    payload = (
        b"# Private Security Record\n\n"
        b"Owner-only verification value: "
        b"PRIVATE-SECURITY-7319"
    )

    response = client.post(
        "/api/v1/documents/upload",
        headers=headers,
        files={
            "file": (
                "private-security.md",
                payload,
                "text/markdown",
            ),
        },
    )

    assert response.status_code == 201

    return response.json()["id"], payload


def create_conversation(
    client: TestClient,
    headers: dict[str, str],
) -> str:
    response = client.post(
        "/api/v1/conversations",
        headers=headers,
        json={
            "title": "Owner private conversation",
            "mode": "normal",
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def create_memory(
    client: TestClient,
    headers: dict[str, str],
) -> str:
    response = client.post(
        "/api/v1/memories",
        headers=headers,
        json={
            "kind": "preference",
            "content": "Owner prefers private mode.",
            "importance": 0.7,
            "confidence": 1.0,
        },
    )

    assert response.status_code == 201

    return response.json()["id"]


def request(
    client: TestClient,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    payload: dict[str, object] | None = None,
):
    kwargs: dict[str, object] = {}

    if headers is not None:
        kwargs["headers"] = headers

    if payload is not None:
        kwargs["json"] = payload

    return client.request(
        method,
        path,
        **kwargs,
    )


def test_document_cross_user_isolation_matrix(
    client: TestClient,
) -> None:
    owner_headers = create_auth_headers(
        client,
        suffix="security-doc-owner",
    )

    attacker_headers = create_auth_headers(
        client,
        suffix="security-doc-attacker",
    )

    document_id, payload = (
        upload_private_document(
            client,
            owner_headers,
        )
    )

    attacks = [
        (
            "GET",
            f"/api/v1/documents/{document_id}",
            None,
        ),
        (
            "GET",
            (
                "/api/v1/documents/"
                f"{document_id}/content"
            ),
            None,
        ),
        (
            "POST",
            (
                "/api/v1/documents/"
                f"{document_id}/process"
            ),
            None,
        ),
        (
            "GET",
            (
                "/api/v1/documents/"
                f"{document_id}/units"
            ),
            None,
        ),
        (
            "DELETE",
            f"/api/v1/documents/{document_id}",
            None,
        ),
    ]

    for method, path, body in attacks:
        response = request(
            client,
            method,
            path,
            headers=attacker_headers,
            payload=body,
        )

        assert response.status_code == 404, (
            method,
            path,
            response.status_code,
            response.text,
        )

    attacker_list = client.get(
        "/api/v1/documents",
        headers=attacker_headers,
    )

    assert attacker_list.status_code == 200
    assert attacker_list.json()["total"] == 0
    assert attacker_list.json()["items"] == []

    owner_read = client.get(
        f"/api/v1/documents/{document_id}",
        headers=owner_headers,
    )

    assert owner_read.status_code == 200
    assert owner_read.json()["status"] == "uploaded"

    owner_content = client.get(
        (
            "/api/v1/documents/"
            f"{document_id}/content"
        ),
        headers=owner_headers,
    )

    assert owner_content.status_code == 200
    assert owner_content.content == payload


def test_conversation_cross_user_isolation_matrix(
    client: TestClient,
) -> None:
    owner_headers = create_auth_headers(
        client,
        suffix="security-chat-owner",
    )

    attacker_headers = create_auth_headers(
        client,
        suffix="security-chat-attacker",
    )

    conversation_id = create_conversation(
        client,
        owner_headers,
    )

    attacks = [
        (
            "GET",
            (
                "/api/v1/conversations/"
                f"{conversation_id}"
            ),
            None,
        ),
        (
            "GET",
            (
                "/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            None,
        ),
        (
            "POST",
            (
                "/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            {
                "content": (
                    "Attempt to access owner chat"
                ),
            },
        ),
        (
            "PATCH",
            (
                "/api/v1/conversations/"
                f"{conversation_id}"
            ),
            {
                "title": "Attacker changed title",
            },
        ),
        (
            "DELETE",
            (
                "/api/v1/conversations/"
                f"{conversation_id}"
            ),
            None,
        ),
    ]

    for method, path, body in attacks:
        response = request(
            client,
            method,
            path,
            headers=attacker_headers,
            payload=body,
        )

        assert response.status_code == 404, (
            method,
            path,
            response.status_code,
            response.text,
        )

    attacker_list = client.get(
        "/api/v1/conversations",
        headers=attacker_headers,
    )

    assert attacker_list.status_code == 200
    assert attacker_list.json() == []

    owner_read = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}"
        ),
        headers=owner_headers,
    )

    assert owner_read.status_code == 200

    assert (
        owner_read.json()["title"]
        == "Owner private conversation"
    )

    owner_messages = client.get(
        (
            "/api/v1/conversations/"
            f"{conversation_id}/messages"
        ),
        headers=owner_headers,
    )

    assert owner_messages.status_code == 200
    assert owner_messages.json() == []


def test_memory_cross_user_isolation_matrix(
    client: TestClient,
) -> None:
    owner_headers = create_auth_headers(
        client,
        suffix="security-memory-owner",
    )

    attacker_headers = create_auth_headers(
        client,
        suffix="security-memory-attacker",
    )

    memory_id = create_memory(
        client,
        owner_headers,
    )

    attacker_list = client.get(
        "/api/v1/memories",
        headers=attacker_headers,
    )

    assert attacker_list.status_code == 200
    assert attacker_list.json() == []

    attacks = [
        (
            "GET",
            f"/api/v1/memories/{memory_id}",
            None,
        ),
        (
            "PATCH",
            f"/api/v1/memories/{memory_id}",
            {
                "content": "Attacker modified it.",
            },
        ),
        (
            "DELETE",
            f"/api/v1/memories/{memory_id}",
            None,
        ),
    ]

    for method, path, body in attacks:
        response = request(
            client,
            method,
            path,
            headers=attacker_headers,
            payload=body,
        )

        assert response.status_code == 404, (
            method,
            path,
            response.status_code,
            response.text,
        )

    owner_read = client.get(
        f"/api/v1/memories/{memory_id}",
        headers=owner_headers,
    )

    assert owner_read.status_code == 200

    assert (
        owner_read.json()["content"]
        == "Owner prefers private mode."
    )


def test_direct_object_routes_require_authentication(
    client: TestClient,
) -> None:
    owner_headers = create_auth_headers(
        client,
        suffix="security-auth-owner",
    )

    document_id, _ = upload_private_document(
        client,
        owner_headers,
    )

    conversation_id = create_conversation(
        client,
        owner_headers,
    )

    memory_id = create_memory(
        client,
        owner_headers,
    )

    protected_requests = [
        (
            "GET",
            f"/api/v1/documents/{document_id}",
            None,
        ),
        (
            "GET",
            (
                "/api/v1/documents/"
                f"{document_id}/content"
            ),
            None,
        ),
        (
            "POST",
            (
                "/api/v1/documents/"
                f"{document_id}/process"
            ),
            None,
        ),
        (
            "GET",
            (
                "/api/v1/documents/"
                f"{document_id}/units"
            ),
            None,
        ),
        (
            "DELETE",
            f"/api/v1/documents/{document_id}",
            None,
        ),
        (
            "GET",
            (
                "/api/v1/conversations/"
                f"{conversation_id}"
            ),
            None,
        ),
        (
            "GET",
            (
                "/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            None,
        ),
        (
            "POST",
            (
                "/api/v1/conversations/"
                f"{conversation_id}/messages"
            ),
            {
                "content": "No token",
            },
        ),
        (
            "PATCH",
            (
                "/api/v1/conversations/"
                f"{conversation_id}"
            ),
            {
                "title": "No token",
            },
        ),
        (
            "DELETE",
            (
                "/api/v1/conversations/"
                f"{conversation_id}"
            ),
            None,
        ),
        (
            "GET",
            f"/api/v1/memories/{memory_id}",
            None,
        ),
        (
            "PATCH",
            f"/api/v1/memories/{memory_id}",
            {
                "content": "No token",
            },
        ),
        (
            "DELETE",
            f"/api/v1/memories/{memory_id}",
            None,
        ),
    ]

    for method, path, body in protected_requests:
        response = request(
            client,
            method,
            path,
            payload=body,
        )

        assert response.status_code == 401, (
            method,
            path,
            response.status_code,
            response.text,
        )


def test_random_object_ids_fail_closed(
    client: TestClient,
) -> None:
    headers = create_auth_headers(
        client,
        suffix="security-random-id-user",
    )

    random_id = (
        "00000000-0000-0000-0000-"
        "000000000000"
    )

    requests = [
        (
            "GET",
            f"/api/v1/documents/{random_id}",
            None,
        ),
        (
            "GET",
            (
                "/api/v1/documents/"
                f"{random_id}/content"
            ),
            None,
        ),
        (
            "POST",
            (
                "/api/v1/documents/"
                f"{random_id}/process"
            ),
            None,
        ),
        (
            "GET",
            (
                "/api/v1/documents/"
                f"{random_id}/units"
            ),
            None,
        ),
        (
            "DELETE",
            f"/api/v1/documents/{random_id}",
            None,
        ),
        (
            "GET",
            (
                "/api/v1/conversations/"
                f"{random_id}"
            ),
            None,
        ),
        (
            "GET",
            (
                "/api/v1/conversations/"
                f"{random_id}/messages"
            ),
            None,
        ),
        (
            "PATCH",
            (
                "/api/v1/conversations/"
                f"{random_id}"
            ),
            {
                "title": "Missing",
            },
        ),
        (
            "DELETE",
            (
                "/api/v1/conversations/"
                f"{random_id}"
            ),
            None,
        ),
        (
            "GET",
            f"/api/v1/memories/{random_id}",
            None,
        ),
        (
            "PATCH",
            f"/api/v1/memories/{random_id}",
            {
                "content": "Missing",
            },
        ),
        (
            "DELETE",
            f"/api/v1/memories/{random_id}",
            None,
        ),
    ]

    for method, path, body in requests:
        response = request(
            client,
            method,
            path,
            headers=headers,
            payload=body,
        )

        assert response.status_code == 404, (
            method,
            path,
            response.status_code,
            response.text,
        )
