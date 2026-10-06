"""
Cycle detection utilities for the prerequisite graph.
Uses DFS-based cycle detection and topological sort (Kahn's algorithm).
"""
from __future__ import annotations
from collections import deque


def has_cycle(adj: dict[str, list[str]]) -> bool:
    """
    Return True if the directed graph has a cycle.
    adj: adjacency list {node_id: [neighbor_id, ...]}
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in adj}

    def dfs(u: str) -> bool:
        color[u] = GRAY
        for v in adj.get(u, []):
            if v not in color:
                color[v] = WHITE
            if color[v] == GRAY:
                return True   # back edge → cycle
            if color[v] == WHITE and dfs(v):
                return True
        color[u] = BLACK
        return False

    for node in list(adj.keys()):
        if color.get(node, WHITE) == WHITE:
            if dfs(node):
                return True
    return False


def topological_sort(adj: dict[str, list[str]]) -> list[str] | None:
    """
    Kahn's algorithm topological sort.
    Returns ordered list, or None if graph has a cycle.
    """
    in_degree: dict[str, int] = {n: 0 for n in adj}
    for u in adj:
        for v in adj[u]:
            if v not in in_degree:
                in_degree[v] = 0
            in_degree[v] += 1

    queue = deque(n for n, d in in_degree.items() if d == 0)
    order: list[str] = []

    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj.get(u, []):
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)

    if len(order) != len(in_degree):
        return None   # cycle detected
    return order


def remove_cycles(adj: dict[str, list[str]]) -> dict[str, list[str]]:
    """
    Return a copy of adj with edges removed until no cycles exist.
    Uses greedy DFS; removes the back edge that closes a cycle.
    """
    result: dict[str, list[str]] = {n: list(vs) for n, vs in adj.items()}

    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {}

    def dfs(u: str):
        color[u] = GRAY
        for v in list(result.get(u, [])):
            if v not in color:
                color[v] = WHITE
            if color.get(v) == GRAY:
                # Remove back edge
                result[u].remove(v)
            elif color.get(v, WHITE) == WHITE:
                dfs(v)
        color[u] = BLACK

    for node in list(result.keys()):
        if color.get(node, WHITE) == WHITE:
            dfs(node)

    return result
