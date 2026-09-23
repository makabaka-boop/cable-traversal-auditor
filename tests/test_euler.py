"""Tests for the Eulerian-walk domain logic.

The important cross-check is exhaustive ("穷举对拍"): for small graphs a
deliberately independent brute-force enumerator visits *every* possible
walk and computes the true minimum; the production algorithm must agree.
The enumerator is test-only -- the implementation never enumerates walks.
"""

from __future__ import annotations

import random
from collections import defaultdict
from itertools import combinations_with_replacement

from app.euler import Disconnected, Jumper, OddDegree, Walk, find_walk

# ---------------------------------------------------------------------------
# Independent brute-force reference implementation (test-only)
# ---------------------------------------------------------------------------


def reference_solve(connectors, jumpers):
    """Solve the same problem with naive, obviously-correct code.

    Returns tuples so comparison is exact:
      ("OK", start, (connectors...), (jumper ids...))
      ("DISCONNECTED", (w1, w2), component_count)
      ("ODD_DEGREE", (odd connectors...))
    """
    bk = lambda s: s.encode("utf-8")
    degree = defaultdict(int)
    neighbours = defaultdict(list)  # connector -> list of (other, edge_index)
    for i, j in enumerate(jumpers):
        degree[j.a] += 1
        degree[j.b] += 1
        neighbours[j.a].append((j.b, i))
        neighbours[j.b].append((j.a, i))

    edge_bearing = [c for c in connectors if degree[c] > 0]

    # Connectivity (zero-degree vertices ignored), plain DFS.
    seen = set()
    components = []
    for seed in sorted(edge_bearing, key=bk):
        if seed in seen:
            continue
        queue = [seed]
        seen.add(seed)
        members = []
        while queue:
            u = queue.pop()
            members.append(u)
            for v, _ in neighbours[u]:
                if v not in seen:
                    seen.add(v)
                    queue.append(v)
        components.append(members)
    if len(components) > 1:
        mins = sorted((min(m, key=bk) for m in components), key=bk)
        return ("DISCONNECTED", (mins[0], mins[1]), len(components))

    odd = sorted((c for c in edge_bearing if degree[c] % 2 == 1), key=bk)
    if len(odd) not in (0, 2):
        return ("ODD_DEGREE", tuple(odd))

    start = odd[0] if odd else min(edge_bearing, key=bk)

    # Enumerate every walk that uses all jumpers exactly once.
    used = [False] * len(jumpers)
    best = None  # ((vertex bytes...), (jumper-id bytes...), vertices, ids)

    def dfs(u, verts, jids):
        nonlocal best
        if len(jids) == len(jumpers):
            key = (tuple(map(bk, verts)), tuple(map(bk, jids)))
            if best is None or key < best[0]:
                best = (key, tuple(verts), tuple(jids))
            return
        for i, j in enumerate(jumpers):
            if used[i]:
                continue
            if j.a == u:
                v = j.b
            elif j.b == u:
                v = j.a
            else:
                continue
            used[i] = True
            verts.append(v)
            jids.append(j.id)
            dfs(v, verts, jids)
            jids.pop()
            verts.pop()
            used[i] = False

    dfs(start, [start], [])
    assert best is not None, "Eulerian graph must admit a complete walk"
    return ("OK", start, best[1], best[2])


def algorithm_solve(connectors, jumpers):
    result = find_walk(list(connectors), list(jumpers))
    if isinstance(result, Walk):
        return ("OK", result.start, result.connectors, result.jumpers)
    if isinstance(result, Disconnected):
        return ("DISCONNECTED", result.witness, result.components)
    assert isinstance(result, OddDegree)
    return ("ODD_DEGREE", result.odd_connectors)


def assert_valid_walk(connectors, jumpers, result):
    """Structural invariants of an OK result, independent of minimality."""
    status, start, verts, jids = result
    assert status == "OK"
    m = len(jumpers)
    assert verts[0] == start
    assert len(verts) == m + 1
    assert len(jids) == m
    assert len(set(jids)) == m, "every jumper used once"
    by_id = {j.id: j for j in jumpers}
    assert set(jids) == set(by_id)
    for u, jid, v in zip(verts, jids, verts[1:]):
        edge = by_id[jid]
        assert (u, v) == (edge.a, edge.b) or (u, v) == (edge.b, edge.a), (
            f"{u} --{jid}--> {v} does not match jumper"
        )
    assert set(verts) <= set(connectors)


# ---------------------------------------------------------------------------
# Exhaustive systematic sweep over every small multigraph
# ---------------------------------------------------------------------------

# Vertices A,B,C; every possible undirected edge type (includes self-loops).
SWEEP_VERTICES = ["A", "B", "C"]
EDGE_TYPES = [
    ("A", "A"),
    ("A", "B"),
    ("A", "C"),
    ("B", "B"),
    ("B", "C"),
    ("C", "C"),
]


def _multiset_graphs(max_edges):
    for size in range(1, max_edges + 1):
        for combo in combinations_with_replacement(range(len(EDGE_TYPES)), size):
            yield [EDGE_TYPES[i] for i in combo]


def _make_jumpers(endpoint_pairs, id_order):
    ids = [f"w{i}" for i in id_order[: len(endpoint_pairs)]]
    return [Jumper(id=ids[k], a=a, b=b) for k, (a, b) in enumerate(endpoint_pairs)]


def test_exhaustive_sweep_canonical_ids():
    """Every multigraph on 3 vertices with 1..4 edges, canonical ids."""
    checked = 0
    for pairs in _multiset_graphs(4):
        jumpers = _make_jumpers(pairs, list(range(1, 9)))
        got = algorithm_solve(SWEEP_VERTICES, jumpers)
        want = reference_solve(SWEEP_VERTICES, jumpers)
        assert got == want
        if got[0] == "OK":
            assert_valid_walk(SWEEP_VERTICES, jumpers, got)
        checked += 1
    assert checked == 6 + 21 + 56 + 126


def test_exhaustive_sweep_shuffled_ids_and_orders():
    """Same graphs, but parallel edges receive shuffled ids and batches
    arrive shuffled -- the result must stay the byte-order minimum."""
    rng = random.Random(20260923)
    checked = 0
    for pairs in _multiset_graphs(4):
        id_order = list(range(1, len(pairs) + 1))
        rng.shuffle(id_order)
        jumpers = _make_jumpers(pairs, id_order)
        order = list(range(len(jumpers)))
        rng.shuffle(order)
        shuffled = [jumpers[i] for i in order]
        vertices = list(SWEEP_VERTICES)
        rng.shuffle(vertices)
        got = algorithm_solve(vertices, shuffled)
        want = reference_solve(vertices, shuffled)
        assert got == want
        if got[0] == "OK":
            assert_valid_walk(vertices, shuffled, got)
        checked += 1
    assert checked == 209


# ---------------------------------------------------------------------------
# Randomised fuzzing on a pool that breaks natural / case assumptions
# ---------------------------------------------------------------------------

FUZZ_POOL = ["A", "B", "C", "D", "J2", "J10", "z", "a", "MM", "x"]
ISOLATED_POOL = ["iso-A", "iso-B", "iso-C"]


def _random_batch(rng, max_edges=8):
    k = rng.randint(2, 6)
    names = rng.sample(FUZZ_POOL, k=k)
    m = rng.randint(1, max_edges)

    id_numbers = rng.sample(range(1, 100), m)  # unique ids: w1, w10, w2, ...
    jumpers = []
    for n in id_numbers:
        a = rng.choice(names)
        b = a if rng.random() < 0.12 else rng.choice(names)
        jumpers.append(Jumper(id=f"w{n}", a=a, b=b))

    connectors = list(names)
    for iso in rng.sample(ISOLATED_POOL, k=rng.randint(0, 2)):
        if iso not in connectors:
            connectors.append(iso)

    rng.shuffle(jumpers)
    rng.shuffle(connectors)
    return connectors, jumpers


def test_randomised_exhaustive_cross_check():
    rng = random.Random(0xC0FFEE)
    feasible = 0
    infeasible = 0
    for _ in range(320):
        connectors, jumpers = _random_batch(rng, max_edges=8)
        got = algorithm_solve(connectors, jumpers)
        want = reference_solve(connectors, jumpers)
        assert got == want, (connectors, jumpers, got, want)
        if got[0] == "OK":
            assert_valid_walk(connectors, jumpers, got)
            feasible += 1
        else:
            infeasible += 1
    # The fuzz pool must actually exercise every verdict branch.
    assert feasible > 0 and infeasible > 0


def test_result_independent_of_input_order():
    rng = random.Random(424242)
    for _ in range(60):
        connectors, jumpers = _random_batch(rng, max_edges=8)
        first = algorithm_solve(connectors, jumpers)
        reordered_jumpers = list(reversed(jumpers))
        reordered_connectors = list(reversed(connectors))
        second = algorithm_solve(reordered_connectors, reordered_jumpers)
        assert first == second


# ---------------------------------------------------------------------------
# Hand-crafted cases
# ---------------------------------------------------------------------------


def _jumpers(*triples):
    return [Jumper(id=jid, a=a, b=b) for jid, a, b in triples]


def test_single_self_loop():
    result = find_walk(["X"], _jumpers(("w1", "X", "X")))
    assert isinstance(result, Walk)
    assert result.start == "X"
    assert result.connectors == ("X", "X")
    assert result.jumpers == ("w1",)


def test_parallel_jumper_id_byte_order_is_tiebreak():
    # "w10" < "w2" in UTF-8 byte order although 10 > 2 numerically.
    jumpers = _jumpers(("w10", "A", "B"), ("w2", "A", "B"))
    result = find_walk(["A", "B"], jumpers)
    assert isinstance(result, Walk)
    assert result.start == "A"
    assert result.connectors == ("A", "B", "A")
    assert result.jumpers == ("w10", "w2")


def test_bowtie_circuit_splices_second_triangle():
    jumpers = _jumpers(
        ("t1", "A", "B"),
        ("t2", "B", "C"),
        ("t3", "C", "A"),
        ("t4", "A", "D"),
        ("t5", "D", "E"),
        ("t6", "E", "A"),
    )
    result = find_walk(["A", "B", "C", "D", "E"], jumpers)
    assert isinstance(result, Walk)
    assert result.start == "A"
    assert result.connectors == ("A", "B", "C", "A", "D", "E", "A")
    assert result.jumpers == ("t1", "t2", "t3", "t4", "t5", "t6")


def test_bridge_to_odd_side_is_postponed():
    # Crossing S-A first strands the S-C pair, so the minimum walk must
    # exhaust S's cycle before crossing, even though edge x1 to A is
    # lexicographically tempting at S.
    jumpers = _jumpers(
        ("x1", "S", "A"),
        ("x2", "A", "B"),
        ("x3", "A", "B"),
        ("x4", "S", "C"),
        ("x5", "S", "C"),
    )
    result = find_walk(["S", "A", "B", "C"], jumpers)
    assert isinstance(result, Walk)
    assert result.start == "A"  # odd connectors are A and S; A is smaller
    assert result.connectors == ("A", "B", "A", "S", "C", "S")
    assert result.jumpers == ("x2", "x3", "x1", "x4", "x5")


def test_zero_degree_connectors_ignored():
    jumpers = _jumpers(("w1", "A", "B"))
    result = find_walk(["C", "A", "B"], jumpers)
    assert isinstance(result, Walk)
    assert result.start == "A"
    assert result.connectors == ("A", "B")
    assert result.jumpers == ("w1",)


def test_disconnected_witness_and_component_count():
    jumpers = _jumpers(
        ("w1", "B", "A"),  # component 1: A,B (minimum A)
        ("w2", "D", "C"),  # component 2: C,D (minimum C)
        ("w3", "E", "E"),  # component 3: E (self-loop, minimum E)
    )
    result = find_walk(["A", "B", "C", "D", "E", "Z"], jumpers)
    assert isinstance(result, Disconnected)
    assert result.components == 3
    assert result.witness == ("A", "C")  # Z is zero-degree, ignored


def test_odd_degree_reports_all_sorted_by_bytes():
    # Star centred at A plus a fourth leaf -> four odd connectors.
    jumpers = _jumpers(
        ("w1", "A", "B"),
        ("w2", "A", "C"),
        ("w3", "A", "D"),
    )
    result = find_walk(["A", "B", "C", "D"], jumpers)
    assert isinstance(result, OddDegree)
    assert result.odd_connectors == ("A", "B", "C", "D")


def test_disconnected_takes_precedence_over_odd_degree():
    # Two components, and the graph as a whole has four odd connectors:
    # the fixed order demands DISCONNECTED first.
    jumpers = _jumpers(
        ("w1", "A", "B"),
        ("w2", "A", "C"),  # component 1: star at A, odd A,B,C
        ("w3", "D", "E"),  # component 2: single edge, odd D,E
    )
    result = find_walk(["A", "B", "C", "D", "E"], jumpers)
    assert isinstance(result, Disconnected)
    assert result.witness == ("A", "D")


def test_start_is_smallest_edge_bearing_connector_for_circuit():
    jumpers = _jumpers(
        ("w1", "B", "C"), ("w2", "C", "A"), ("w3", "A", "B")
    )
    result = find_walk(["A", "B", "C", "isolated"], jumpers)
    assert isinstance(result, Walk)
    assert result.start == "A"


def test_utf8_byte_order_not_numeric_order():
    # Byte order: "J10" < "J2" because '1' (0x31) < '2' (0x32).
    jumpers = _jumpers(("w1", "J2", "J10"))
    result = find_walk(["J2", "J10"], jumpers)
    assert isinstance(result, Walk)
    assert result.start == "J10"
    assert result.connectors == ("J10", "J2")


def test_utf8_byte_order_uppercase_before_lowercase():
    jumpers = _jumpers(("w1", "z", "A"))
    result = find_walk(["z", "A"], jumpers)
    assert isinstance(result, Walk)
    assert result.start == "A"  # 0x41 < 0x7A
    assert result.connectors == ("A", "z")


def test_largest_eulerian_batch_is_linear_time_smoke():
    # 300 connectors / 3000 jumpers at the documented upper bound:
    # ten rounds of a 300-cycle, every degree 20, must return promptly.
    connectors = [f"c{i:03d}" for i in range(300)]
    jumpers = [
        Jumper(id=f"j{i:04d}", a=connectors[i % 300], b=connectors[(i + 1) % 300])
        for i in range(3000)
    ]
    result = find_walk(connectors, jumpers)
    assert isinstance(result, Walk)
    assert len(result.jumpers) == 3000
    assert len(result.connectors) == 3001
