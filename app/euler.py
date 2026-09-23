"""Euler-trail verification for the temporary exhibition-hall network."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Jumper:
    id: str
    u: str
    v: str


def connected_components(vertices, jumpers):
    """Return components containing at least one incident edge."""
    adjacency = {vertex: [] for vertex in vertices}
    for jumper in jumpers:
        adjacency[jumper.u].append(jumper.v)
        if jumper.v != jumper.u:
            adjacency[jumper.v].append(jumper.u)

    visited = set()
    components = []
    for start in vertices:
        if start in visited or not adjacency[start]:
            continue

        stack = [start]
        visited.add(start)
        component = []
        while stack:
            vertex = stack.pop()
            component.append(vertex)
            for neighbor in adjacency[vertex]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    stack.append(neighbor)
        components.append(sorted(component))
    return components


def bridge_ids(current, adjacency, active):
    """Find active bridges reachable from current using iterative Tarjan DFS."""
    discovery = {current: 1}
    low = {current: 1}
    timer = 1
    bridges = set()
    # (vertex, edge used to enter it, next adjacency position)
    stack = [(current, None, 0)]

    while stack:
        vertex, incoming_edge, position = stack[-1]
        neighbors = adjacency[vertex]

        if position == len(neighbors):
            stack.pop()
            if stack and incoming_edge is not None:
                parent = stack[-1][0]
                if low[vertex] < low[parent]:
                    low[parent] = low[vertex]
                if low[vertex] > discovery[parent]:
                    bridges.add(incoming_edge)
            continue

        neighbor, edge_id = neighbors[position]
        stack[-1] = (vertex, incoming_edge, position + 1)
        if not active[edge_id] or edge_id == incoming_edge:
            continue

        if neighbor in discovery:
            if discovery[neighbor] < low[vertex]:
                low[vertex] = discovery[neighbor]
        else:
            timer += 1
            discovery[neighbor] = low[neighbor] = timer
            stack.append((neighbor, edge_id, 0))

    return bridges


def minimum_euler_trail(vertices, jumpers, start):
    """Find the lexicographically minimum Euler trail.

    A trail is ordered first by its UTF-8 encoded connector sequence, then by
    its UTF-8 encoded jumper-id sequence. Fleury's algorithm never cuts a
    bridge while another edge remains; at each step it chooses the smallest
    admissible endpoint and then the smallest edge id. It does not enumerate
    permutations.
    """
    # For a non-loop, the other endpoint depends on the current vertex; store
    # each direction separately while retaining deterministic sorted order.
    ordered_adjacency = {vertex: [] for vertex in vertices}
    bridge_adjacency = {vertex: [] for vertex in vertices}
    for jumper in jumpers:
        ordered_adjacency[jumper.u].append(
            (jumper.v.encode("utf-8"), jumper.id.encode("utf-8"), jumper)
        )
        bridge_adjacency[jumper.u].append((jumper.v, jumper.id))
        if jumper.v != jumper.u:
            ordered_adjacency[jumper.v].append(
                (jumper.u.encode("utf-8"), jumper.id.encode("utf-8"), jumper)
            )
            bridge_adjacency[jumper.v].append((jumper.u, jumper.id))

    for edges in ordered_adjacency.values():
        edges.sort(key=lambda item: (item[0], item[1]))

    active = {jumper.id: True for jumper in jumpers}
    current = start
    path_vertices = [start]
    path_edges = []

    for _ in jumpers:
        candidates = [
            item
            for item in ordered_adjacency[current]
            if active[item[2].id]
        ]

        if len(candidates) == 1:
            admissible = candidates
        else:
            bridges = bridge_ids(current, bridge_adjacency, active)
            admissible = [
                (target_bytes, edge_bytes, jumper)
                for target_bytes, edge_bytes, jumper in candidates
                if jumper.id not in bridges or jumper.v == jumper.u
            ]
            if not admissible:
                # Only the unavoidable final bridge may remain.
                admissible = candidates

        _, _, chosen = admissible[0]
        active[chosen.id] = False
        current = chosen.v if current == chosen.u else chosen.u
        path_edges.append(chosen.id)
        path_vertices.append(current)

    return path_vertices, path_edges


def verify(vertices, jumpers):
    """Validate graph topology and produce the deterministic inspection trail."""
    components = connected_components(vertices, jumpers)

    # Isolated connectors are ignored for topology, as required. If there are
    # more than two active components, report the two smallest component minima.
    if len(components) > 1:
        components.sort(key=lambda component: component[0].encode("utf-8"))
        return {
            "status": "DISCONNECTED",
            "connector": components[0][0],
            "other_connector": components[1][0],
        }

    degrees = {vertex: 0 for vertex in vertices}
    for jumper in jumpers:
        degrees[jumper.u] += 1
        degrees[jumper.v] += 1

    odd_vertices = sorted(
        (vertex for vertex, degree in degrees.items() if degree % 2),
        key=lambda vertex: vertex.encode("utf-8"),
    )
    if len(odd_vertices) not in (0, 2):
        return {"status": "ODD_DEGREE", "connectors": odd_vertices}

    edged_vertices = sorted(
        (vertex for vertex, degree in degrees.items() if degree > 0),
        key=lambda vertex: vertex.encode("utf-8"),
    )
    start = odd_vertices[0] if odd_vertices else edged_vertices[0]
    path_vertices, path_edges = minimum_euler_trail(vertices, jumpers, start)
    return {
        "status": "FEASIBLE",
        "start": start,
        "connectors": path_vertices,
        "jumper_ids": path_edges,
    }
