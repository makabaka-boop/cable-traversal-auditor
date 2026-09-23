import random

import pytest

from app.euler import Jumper, verify


def test_single_edge_starts_at_minimum_endpoint():
    result = verify(
        ["B", "A"],
        [Jumper("j1", "A", "B")],
    )

    assert result == {
        "status": "FEASIBLE",
        "start": "A",
        "connectors": ["A", "B"],
        "jumper_ids": ["j1"],
    }


def test_self_loop_does_not_create_odd_degree_and_is_in_trail():
    result = verify(["A"], [Jumper("loop", "A", "A")])

    assert result["status"] == "FEASIBLE"
    assert result["start"] == "A"
    assert result["connectors"] == ["A", "A"]
    assert result["jumper_ids"] == ["loop"]


def test_parallel_edges_are_tied_broken_by_jumper_id():
    result = verify(
        ["A", "B"],
        [
            Jumper("second", "A", "B"),
            Jumper("first", "B", "A"),
        ],
    )

    assert result["status"] == "FEASIBLE"
    assert result["connectors"] == ["A", "B", "A"]
    assert result["jumper_ids"] == ["first", "second"]


def test_bridge_is_saved_until_no_cycle_edge_remains():
    # At B, taking C via the bridge immediately strands the B-A cycle.
    result = verify(
        ["A", "B", "C", "D"],
        [
            Jumper("bridge", "B", "C"),
            Jumper("edge-a", "A", "B"),
            Jumper("edge-b", "B", "D"),
            Jumper("edge-c", "D", "A"),
            Jumper("edge-d", "C", "C"),
        ],
    )

    assert result["status"] == "FEASIBLE"
    assert result["connectors"] == ["B", "A", "D", "B", "C", "C"]
    assert result["jumper_ids"] == [
        "edge-a",
        "edge-c",
        "edge-b",
        "bridge",
        "edge-d",
    ]


def test_isolated_connector_is_ignored_by_connectivity():
    result = verify(
        ["A", "B", "isolated"],
        [Jumper("x", "A", "B")],
    )

    assert result["status"] == "FEASIBLE"
    assert result["start"] == "A"


def test_disconnected_reports_minimum_connectors_from_two_edge_components():
    result = verify(
        ["C1", "D", "A2", "B"],
        [
            Jumper("left", "C1", "D"),
            Jumper("right", "B", "A2"),
        ],
    )

    assert result == {
        "status": "DISCONNECTED",
        "connector": "A2",
        "other_connector": "C1",
    }


def test_disconnected_takes_precedence_over_odd_degree():
    result = verify(
        ["A", "B", "C", "D", "E"],
        [
            Jumper("left", "A", "B"),
            Jumper("right", "C", "D"),
            Jumper("loop", "E", "E"),
        ],
    )

    assert result["status"] == "DISCONNECTED"
    assert result["connector"] == "A"
    assert result["other_connector"] == "C"


def test_disconnected_uses_two_smallest_component_minima():
    result = verify(
        ["C", "Z", "A", "M", "D"],
        [
            Jumper("first", "C", "Z"),
            Jumper("second", "A", "M"),
            Jumper("third", "D", "D"),
        ],
    )

    assert result == {
        "status": "DISCONNECTED",
        "connector": "A",
        "other_connector": "C",
    }


def test_odd_degree_reports_all_sorted_connectors():
    # Four odd vertices: A(1), C(1), D(1), E(1); B has degree 4.
    result = verify(
        ["D", "C", "B", "A", "E"],
        [
            Jumper("a", "A", "B"),
            Jumper("b", "B", "C"),
            Jumper("c", "B", "D"),
            Jumper("d", "B", "E"),
        ],
    )

    assert result == {
        "status": "ODD_DEGREE",
        "connectors": ["A", "C", "D", "E"],
    }


def test_even_circuit_starts_at_minimum_edged_connector():
    result = verify(
        ["C", "A", "B"],
        [
            Jumper("a-b", "A", "B"),
            Jumper("b-c", "B", "C"),
            Jumper("c-a", "C", "A"),
        ],
    )

    assert result["status"] == "FEASIBLE"
    assert result["start"] == "A"
    assert result["connectors"][0] == "A"
    assert result["connectors"][-1] == "A"


def test_input_order_does_not_change_output():
    jumpers = [
        Jumper("j1", "A", "B"),
        Jumper("j2", "B", "C"),
        Jumper("j3", "C", "A"),
        Jumper("loop", "A", "A"),
    ]
    shuffled = [jumpers[2], jumpers[0], jumpers[3], jumpers[1]]

    assert verify(["C", "A", "B"], jumpers) == verify(["A", "B", "C"], shuffled)


def test_unicode_utf8_ordering_for_jumper_ids():
    result = verify(
        ["A", "B"],
        [
            Jumper("é", "A", "B"),
            Jumper("z", "B", "A"),
        ],
    )

    assert result["jumper_ids"] == ["z", "é"]


def brute_force_minimum(vertices, jumpers):
    """Reference search for tiny graphs; cost is factorial in edge count."""
    by_id = {jumper.id: jumper for jumper in jumpers}
    adjacency = {vertex: [] for vertex in vertices}
    for jumper in jumpers:
        adjacency[jumper.u].append(jumper.id)
        if jumper.v != jumper.u:
            adjacency[jumper.v].append(jumper.id)

    degrees = {vertex: 0 for vertex in vertices}
    for jumper in jumpers:
        degrees[jumper.u] += 1
        degrees[jumper.v] += 1
    odd = [vertex for vertex, degree in degrees.items() if degree % 2]
    if odd:
        if len(odd) not in (0, 2):
            starts = []
        else:
            starts = [min(odd, key=lambda value: value.encode())]
    else:
        starts = [
            min(
                (vertex for vertex in vertices if adjacency[vertex]),
                key=lambda value: value.encode(),
            )
        ]

    best = None

    def search(current, used, vertex_path, edge_path):
        nonlocal best
        if len(used) == len(jumpers):
            key = (
                tuple(vertex.encode("utf-8") for vertex in vertex_path),
                tuple(edge_id.encode("utf-8") for edge_id in edge_path),
            )
            if best is None or key < best[0]:
                best = (key, vertex_path.copy(), edge_path.copy())
            return

        for edge_id in sorted(adjacency[current]):
            if edge_id in used:
                continue
            jumper = by_id[edge_id]
            if current == jumper.u:
                nxt = jumper.v
            else:
                nxt = jumper.u
            used.add(edge_id)
            vertex_path.append(nxt)
            edge_path.append(edge_id)
            search(nxt, used, vertex_path, edge_path)
            edge_path.pop()
            vertex_path.pop()
            used.remove(edge_id)

    for start in starts:
        search(start, set(), [start], [])
    return best


def random_case(rng, edge_count):
    labels = ["N0", "N1", "N2", "N3", "N4", "N5"]
    # Isolated vertices are allowed, but include enough active vertices.
    vertex_count = rng.randint(1, min(6, len(labels)))
    vertices = labels[:vertex_count]
    pool = list(range(edge_count))
    rng.shuffle(pool)
    jumpers = []
    for index in range(edge_count):
        u = vertices[rng.randrange(vertex_count)]
        v = vertices[rng.randrange(vertex_count)]
        jumpers.append(Jumper(f"e{pool[index]:02d}", u, v))
    return vertices, jumpers


@pytest.mark.parametrize("seed", range(300))
def test_matches_brute_force_on_small_random_graphs(seed):
    rng = random.Random(seed)
    vertices, jumpers = random_case(rng, rng.randint(1, 7))
    result = verify(vertices, jumpers)
    expected = brute_force_minimum(vertices, jumpers)

    if expected is None:
        assert result["status"] in {"DISCONNECTED", "ODD_DEGREE"}
    else:
        _, expected_vertices, expected_edges = expected
        assert result["status"] == "FEASIBLE"
        assert result["connectors"] == expected_vertices
        assert result["jumper_ids"] == expected_edges
        assert set(result["jumper_ids"]) == {jumper.id for jumper in jumpers}
