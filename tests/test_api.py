from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def verify(payload):
    return client.post("/api/verify", json=payload)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_feasible_response():
    response = verify(
        {
            "connectors": ["B", "A"],
            "jumpers": [{"id": "j1", "u": "A", "v": "B"}],
        }
    )

    assert response.status_code == 200
    assert response.json() == {
        "status": "FEASIBLE",
        "start": "A",
        "connectors": ["A", "B"],
        "jumper_ids": ["j1"],
    }


def test_unknown_connector_returns_422():
    response = verify(
        {
            "connectors": ["A"],
            "jumpers": [{"id": "j1", "u": "A", "v": "X"}],
        }
    )

    assert response.status_code == 422


def test_duplicate_jumper_id_returns_422():
    response = verify(
        {
            "connectors": ["A", "B"],
            "jumpers": [
                {"id": "same", "u": "A", "v": "B"},
                {"id": "same", "u": "B", "v": "A"},
            ],
        }
    )

    assert response.status_code == 422


def test_duplicate_connector_value_returns_422():
    response = verify(
        {
            "connectors": ["A", "A"],
            "jumpers": [{"id": "j1", "u": "A", "v": "A"}],
        }
    )

    assert response.status_code == 422


def test_non_ascii_connector_returns_422():
    response = verify(
        {
            "connectors": ["接头"],
            "jumpers": [{"id": "j1", "u": "接头", "v": "接头"}],
        }
    )

    assert response.status_code == 422


def test_empty_connector_list_returns_422():
    response = verify({"connectors": [], "jumpers": []})
    assert response.status_code == 422


def test_topology_failure_is_not_a_request_validation_error():
    response = verify(
        {
            "connectors": ["A", "B"],
            "jumpers": [
                {"id": "a", "u": "A", "v": "A"},
                {"id": "b", "u": "B", "v": "B"},
            ],
        }
    )

    assert response.status_code == 200
    assert response.json()["status"] == "DISCONNECTED"


def test_unknown_fields_are_rejected():
    response = verify(
        {
            "connectors": ["A", "B"],
            "jumpers": [{"id": "j1", "u": "A", "v": "B", "color": "red"}],
        }
    )

    assert response.status_code == 422


def test_missing_field_returns_422():
    response = verify(
        {"connectors": ["A"], "jumpers": [{"id": "j1", "u": "A"}]}
    )

    assert response.status_code == 422


def test_too_many_connectors_returns_422():
    connectors = [f"N{i}" for i in range(301)]
    response = verify(
        {
            "connectors": connectors,
            "jumpers": [{"id": "j1", "u": "N0", "v": "N1"}],
        }
    )

    assert response.status_code == 422


def test_too_many_jumpers_returns_422():
    jumpers = [{"id": f"j{i}", "u": "N0", "v": "N0"} for i in range(3001)]
    response = verify({"connectors": ["N0"], "jumpers": jumpers})

    assert response.status_code == 422


def test_non_object_body_returns_422():
    response = client.post(
        "/api/verify",
        content="[1, 2, 3]",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422


def test_malformed_json_returns_422():
    response = client.post(
        "/api/verify",
        content="{not json",
        headers={"Content-Type": "application/json"},
    )

    assert response.status_code == 422
