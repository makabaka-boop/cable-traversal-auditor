"""Pure domain logic: Eulerian-walk verification for a temporary exhibition
patch-bay graph.

The graph is an undirected multigraph:

* vertices = connector (接头) names,
* edges    = test jumpers (跳线) with unique ids,
* self-loops and parallel jumpers are allowed.

A "complete walk" uses every jumper exactly once (an Eulerian trail).
The service ignores zero-degree connectors while checking the edge-bearing
part of the graph.

Lexicographic order
--------------------
Two complete walks are compared in UTF-8 byte order by

    1. the connector sequence (primary), then
    2. the jumper-id sequence (secondary).

The minimum such walk is produced by *iterative Hierholzer where the next
edge is always the smallest unused edge ordered by (next connector bytes,
jumper id bytes), output in reverse finish order*. The reversal makes the
walk postpone bridges exactly when they would strand remaining edges, so
the emitted edge at every step is precisely the smallest admissible edge of
Fleury's greedy rule; induction on the edge count proves the output is the
minimum walk. The algorithm is O(E log E) and never enumerates permutations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

# Adjacency entry: (next-connector key, jumper-id key,
#                   next connector, jumper id, jumper index)
AdjEntry = tuple[bytes, bytes, str, str, int]


def _key(value: str) -> bytes:
    """UTF-8 byte-order key (equal to code-point order for ASCII names)."""
    return value.encode("utf-8")


@dataclass(frozen=True)
class Jumper:
    """One undirected jumper between connectors ``a`` and ``b``.

    ``a == b`` is a self-loop; multiple jumpers may share endpoints.
    """

    id: str
    a: str
    b: str


@dataclass(frozen=True)
class Walk:
    """Feasible result: a complete walk covering every jumper once."""

    start: str
    connectors: tuple[str, ...]
    jumpers: tuple[str, ...]


@dataclass(frozen=True)
class Disconnected:
    """Infeasible: the edge-bearing part has more than one component.

    ``witness`` holds the minimum connector of the component with the
    smallest minimum, followed by the minimum connector of the component
    with the second-smallest minimum -- two connectors provably sitting in
    different edge-bearing components.
    """

    witness: tuple[str, str]
    components: int


@dataclass(frozen=True)
class OddDegree:
    """Infeasible: connected, but the odd-degree connectors are not 0 or 2."""

    odd_connectors: tuple[str, ...]


Result = "Walk | Disconnected | OddDegree"


def find_walk(
    connectors: Sequence[str], jumpers: Sequence[Jumper]
) -> Walk | Disconnected | OddDegree:
    """Verify the batch and return the deterministic result.

    Inputs are assumed already validated (unique names, known endpoints,
    unique jumper ids, non-empty batch) -- see :mod:`app.schemas`.
    """
    degree: dict[str, int] = {c: 0 for c in connectors}
    adjacency: dict[str, list[AdjEntry]] = {c: [] for c in connectors}

    for index, jumper in enumerate(jumpers):
        # A self-loop is inserted into both endpoint slots and therefore
        # contributes 2 to the degree, matching the Eulerian convention.
        degree[jumper.a] += 1
        degree[jumper.b] += 1
        id_key = _key(jumper.id)
        adjacency[jumper.a].append(
            (_key(jumper.b), id_key, jumper.b, jumper.id, index)
        )
        adjacency[jumper.b].append(
            (_key(jumper.a), id_key, jumper.a, jumper.id, index)
        )

    edge_bearing = [c for c in connectors if degree[c] > 0]

    # --- Connectivity of the edge-bearing part (zero-degree ignored) ------
    # Sorted seeds keep component discovery independent of input ordering.
    components = _components(adjacency, sorted(edge_bearing, key=_key))
    if len(components) > 1:
        component_mins = sorted(
            (min(members, key=_key) for members in components), key=_key
        )
        return Disconnected(
            witness=(component_mins[0], component_mins[1]),
            components=len(components),
        )

    # --- Odd-degree condition --------------------------------------------
    odd = sorted((c for c in edge_bearing if degree[c] & 1), key=_key)
    if len(odd) not in (0, 2):
        return OddDegree(odd_connectors=tuple(odd))

    start = odd[0] if odd else min(edge_bearing, key=_key)

    # --- Minimum complete walk: smallest-edge-first Hierholzer -----------
    for entries in adjacency.values():
        # Ordering is fully decided by the first two byte keys; jumper ids
        # are unique so (next connector, jumper id) pairs never collide.
        entries.sort()

    used = [False] * len(jumpers)
    cursor: dict[str, int] = {}

    vertex_stack: list[str] = [start]
    arrival_stack: list[str] = []  # jumper id used to enter the top vertex
    finished_vertices: list[str] = []
    finished_jumpers: list[str] = []

    while vertex_stack:
        current = vertex_stack[-1]
        entries = adjacency[current]
        i = cursor.get(current, 0)
        while i < len(entries) and used[entries[i][4]]:
            i += 1
        cursor[current] = i

        if i == len(entries):
            # All edges from this vertex are consumed: finish it.
            finished_vertices.append(vertex_stack.pop())
            if arrival_stack:
                finished_jumpers.append(arrival_stack.pop())
            continue

        _, _, nxt, jumper_id, index = entries[i]
        used[index] = True
        cursor[current] = i + 1
        vertex_stack.append(nxt)
        arrival_stack.append(jumper_id)

    connector_sequence = tuple(reversed(finished_vertices))
    jumper_sequence = tuple(reversed(finished_jumpers))

    return Walk(
        start=start,
        connectors=connector_sequence,
        jumpers=jumper_sequence,
    )


def _components(
    adjacency: dict[str, list[AdjEntry]], seeds: Sequence[str]
) -> list[list[str]]:
    """Connected components reached from ``seeds`` (each is edge-bearing).

    Seeds are explored in the order given; the caller passes them in a
    deterministic order so component numbering never depends on dict hash
    layout or jumper insertion order.
    """
    seen: set[str] = set()
    components: list[list[str]] = []
    for seed in seeds:
        if seed in seen:
            continue
        members: list[str] = []
        stack = [seed]
        seen.add(seed)
        while stack:
            vertex = stack.pop()
            members.append(vertex)
            for _, _, neighbour, _, _ in adjacency[vertex]:
                if neighbour not in seen:
                    seen.add(neighbour)
                    stack.append(neighbour)
        components.append(members)
    return components
