from fastapi.testclient import TestClient


def test_root_endpoint(
    client: TestClient,
) -> None:
    response = client.get("/")

    assert response.status_code == 200

    payload = response.json()

    assert payload["project"] == "Ihsan RAG AI"
    assert payload["status"] == "running"
    assert payload["version"] == "1.0.0"
