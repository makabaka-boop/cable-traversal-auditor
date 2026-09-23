"""HTTP boundary tests for the verification API."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

PATH = "/api/v1/walks/verify"


# ---------------------------------------------------------------------------
# Happy paths and domain verdicts
# ---------------------------------------------------------------------------


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "up"}


def test_ok_minimum_walk():
    payload = {
        "connectors": ["A", "B", "C", "D", "E"],
        "jumpers": [
            {"id": "t6", "endpoints": ["E", "A"]},
            {"id": "t2", "endpoints": ["B", "C"]},
            {"id": "t5", "endpoints": ["D", "E"]},
            {"id": "t1", "endpoints": ["A", "B"]},
            {"id": "t4", "endpoints": ["A", "D"]},
            {"id": "t3", "endpoints": ["C", "A"]},
        ],
    }
    response = client.post(PATH, json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "status": "OK",
        "start": "A",
        "connectors": ["A", "B", "C", "A", "D", "E", "A"],
        "jumpers": ["t1", "t2", "t3", "t4", "t5", "t6"],
    }


def test_ok_self_loop_and_parallel_jumpers():
    payload = {
        "connectors": ["A", "B"],
        "jumpers": [
            {"id": "loop", "endpoints": ["A", "A"]},
            {"id": "p2", "endpoints": ["A", "B"]},
            {"id": "p1", "endpoints": ["B", "A"]},
        ],
    }
    response = client.post(PATH, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert body["start"] == "A"
    assert body["jumpers"] == ["loop", "p1", "p2"]
    assert body["connectors"] == ["A", "A", "B", "A"]


def test_disconnected_is_200_with_witness():
    payload = {
        "connectors": ["A", "B", "C", "D", "Z"],
        "jumpers": [
            {"id": "w1", "endpoints": ["B", "A"]},
            {"id": "w2", "endpoints": ["D", "C"]},
        ],
    }
    response = client.post(PATH, json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "status": "DISCONNECTED",
        "components": 2,
        "witness": ["A", "C"],
    }


def test_odd_degree_is_200_and_lists_all():
    payload = {
        "connectors": ["A", "B", "C", "D"],
        "jumpers": [
            {"id": "w1", "endpoints": ["A", "B"]},
            {"id": "w2", "endpoints": ["A", "C"]},
            {"id": "w3", "endpoints": ["A", "D"]},
        ],
    }
    response = client.post(PATH, json=payload)
    assert response.status_code == 200
    assert response.json() == {
        "status": "ODD_DEGREE",
        "odd_connectors": ["A", "B", "C", "D"],
    }


def test_zero_degree_connectors_are_accepted_but_ignored():
    payload = {
        "connectors": ["spare", "A", "B"],
        "jumpers": [{"id": "w1", "endpoints": ["A", "B"]}],
    }
    response = client.post(PATH, json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert "spare" not in body["connectors"]


def test_response_is_stable_under_jumper_permutation():
    base = {
        "connectors": ["A", "B", "C", "D", "E"],
        "jumpers": [
            {"id": "t1", "endpoints": ["A", "B"]},
            {"id": "t2", "endpoints": ["B", "C"]},
            {"id": "t3", "endpoints": ["C", "A"]},
            {"id": "t4", "endpoints": ["A", "D"]},
            {"id": "t5", "endpoints": ["D", "E"]},
            {"id": "t6", "endpoints": ["E", "A"]},
        ],
    }
    shuffled = {**base, "jumpers": list(reversed(base["jumpers"]))}
    first = client.post(PATH, json=base).json()
    second = client.post(PATH, json=shuffled).json()
    assert first == second


# ---------------------------------------------------------------------------
# 422 boundary: the whole batch is rejected
# ---------------------------------------------------------------------------


def _post(payload):
    return client.post(PATH, json=payload)


def test_422_duplicate_jumper_id():
    payload = {
        "connectors": ["A", "B"],
        "jumpers": [
            {"id": "dup", "endpoints": ["A", "B"]},
            {"id": "dup", "endpoints": ["A", "B"]},
        ],
    }
    response = _post(payload)
    assert response.status_code == 422
    assert "duplicate jumper id" in response.text


def test_422_unknown_connector_endpoint():
    payload = {
        "connectors": ["A", "B"],
        "jumpers": [{"id": "w1", "endpoints": ["A", "X"]}],
    }
    response = _post(payload)
    assert response.status_code == 422
    assert "unknown connector" in response.text


def test_422_duplicate_connector_names():
    payload = {
        "connectors": ["A", "A"],
        "jumpers": [{"id": "w1", "endpoints": ["A", "A"]}],
    }
    assert _post(payload).status_code == 422


def test_422_non_ascii_connector():
    payload = {
        "connectors": ["接头A"],
        "jumpers": [{"id": "w1", "endpoints": ["接头A", "接头A"]}],
    }
    response = _post(payload)
    assert response.status_code == 422
    assert "not ASCII" in response.text


def test_422_empty_connector_name():
    payload = {
        "connectors": [""],
        "jumpers": [{"id": "w1", "endpoints": ["", ""]}],
    }
    assert _post(payload).status_code == 422


def test_422_empty_connector_list():
    payload = {"connectors": [], "jumpers": [{"id": "w1", "endpoints": []}]}
    assert _post(payload).status_code == 422


def test_422_empty_jumper_list():
    payload = {
        "connectors": ["A"],
        "jumpers": [],
    }
    assert _post(payload).status_code == 422


def test_422_endpoints_wrong_arity():
    base_connectors = ["A", "B", "C"]
    for endpoints in ([], ["A"], ["A", "B", "C"]):
        payload = {
            "connectors": base_connectors,
            "jumpers": [{"id": "w1", "endpoints": endpoints}],
        }
        assert _post(payload).status_code == 422


def test_422_wrong_field_types():
    assert _post({"connectors": "AB", "jumpers": []}).status_code == 422
    assert _post(
        {"connectors": ["A"], "jumpers": [{"id": 1, "endpoints": ["A", "A"]}]}
    ).status_code == 422
    assert _post(
        {"connectors": ["A"], "jumpers": [{"id": "w1", "endpoints": "AA"}]}
    ).status_code == 422


def test_422_unknown_and_duplicate_reported_as_single_batch_failure():
    payload = {
        "connectors": ["A", "B"],
        "jumpers": [
            {"id": "w1", "endpoints": ["A", "X"]},
            {"id": "w1", "endpoints": ["A", "B"]},
        ],
    }
    assert _post(payload).status_code == 422


def test_422_extra_fields_forbidden():
    payload = {
        "connectors": ["A"],
        "jumpers": [{"id": "w1", "endpoints": ["A", "A"], "note": "x"}],
    }
    assert _post(payload).status_code == 422
    payload = {"connectors": ["A"], "jumpers": [], "batch": 7}
    assert _post(payload).status_code == 422


def test_422_missing_required_fields():
    assert _post({"jumpers": []}).status_code == 422
    assert _post({"connectors": ["A"]}).status_code == 422
    assert _post(
        {"connectors": ["A"], "jumpers": [{"endpoints": ["A", "A"]}]}
    ).status_code == 422


# ---------------------------------------------------------------------------
# Boundary sizes
# ---------------------------------------------------------------------------


def test_upper_bound_batch_accepted():
    connectors = [f"c{i:03d}" for i in range(300)]
    jumpers = [
        {"id": f"j{i:04d}", "endpoints": [f"c{i % 300:03d}", f"c{(i + 1) % 300:03d}"]}
        for i in range(3000)
    ]
    response = _post({"connectors": connectors, "jumpers": jumpers})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "OK"
    assert len(body["jumpers"]) == 3000
    assert len(body["connectors"]) == 3001
    assert body["start"] == "c000"


def test_422_one_too_many_connectors():
    payload = {
        "connectors": [f"c{i}" for i in range(301)],
        "jumpers": [{"id": "w1", "endpoints": ["c0", "c0"]}],
    }
    assert _post(payload).status_code == 422


def test_422_one_too_many_jumpers():
    connectors = ["A", "B"]
    jumpers = [
        {"id": f"w{i}", "endpoints": ["A", "B"]} for i in range(3001)
    ]
    assert _post({"connectors": connectors, "jumpers": jumpers}).status_code == 422
