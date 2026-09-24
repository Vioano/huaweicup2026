"""Extract unchanged, raw-port-closed attention numerator and FFN islands.

The returned blocks describe original operations; no reduction tree is rebuilt.
An unsafe recognized row raises UnsupportedStructure with its sink ID.
"""
from __future__ import annotations

from .attention_rows import _packed_ffn_motifs
from .construct import UnsupportedStructure


def extract(index, ports, rows):
    """Return disjoint attention-row and FFN records in original graph order."""
    rank = {u: i for i, u in enumerate(index.order)}
    result = []
    occupied = set()

    def ordered(nodes):
        return tuple(sorted(nodes, key=rank.__getitem__))

    def closed(island):
        members = set(island)
        root = island[-1]  # index.order is topological.
        return all(not (ports.consumers[t] - members)
                   for u in members - {root} for t in ports.outputs[u])

    for row in rows:
        sink = row["sink"]
        members = set(row["nodes"])
        try:
            if sink not in members or members & occupied:
                raise ValueError("overlapping or incomplete row")
            parents = index.pred[sink]
            if len(parents) != 2 or any(index.ops[u]["op"] != "ADD" for u in parents):
                raise ValueError("sink has no two original ADD parents")
            values = set(row["v"])

            def subtree(root):
                stack, nodes, leaves = [root], set(), set()
                while stack:
                    u = stack.pop()
                    if u in nodes:
                        raise ValueError("numerator has a repeated node")
                    if u not in members:
                        raise ValueError("numerator leaves the recognized row")
                    nodes.add(u)
                    op = index.ops[u]["op"]
                    if op == "ADD":
                        if len(index.pred[u]) != 2:
                            raise ValueError("numerator ADD is not binary")
                        stack.extend(index.pred[u])
                    elif op == "MATMUL":
                        parents = index.pred[u]
                        if (len(parents) != 2 or len(parents & values) != 1
                                or len([p for p in parents if index.ops[p]["op"] == "EXP"]) != 1):
                            raise ValueError("weighted MATMUL lacks EXP and V parents")
                        leaves.add(u)
                    else:
                        raise ValueError("numerator contains another operation")
                return nodes, leaves

            candidates = []
            for parent in parents:
                try:
                    nodes, leaves = subtree(parent)
                    if len(leaves) < 2 or len(nodes) != 2 * len(leaves) - 1:
                        continue
                    children = ordered(index.pred[parent])
                    if len(children) != 2:
                        continue
                    islands = tuple(ordered(subtree(child)[0]) for child in children)
                    if (set(islands[0]) & set(islands[1])
                            or set(islands[0]) | set(islands[1]) != nodes - {parent}
                            or not all(closed(island) for island in islands)):
                        continue
                    candidates.append(islands)
                except ValueError:
                    continue
            if len(candidates) != 1:
                raise ValueError(f"expected one closed original numerator, found {len(candidates)}")
            result.append({"kind": "attention_row", "nodes": ordered(members),
                           "islands": candidates[0], "sink": sink})
            occupied.update(members)
        except ValueError as exc:
            raise UnsupportedStructure(f"attention row {sink} rejected: {exc}") from exc

    for motif in _packed_ffn_motifs(index, ports, rows):
        nodes = ordered(motif)
        if set(nodes) & occupied or not closed(nodes):
            raise UnsupportedStructure(f"FFN motif {motif[-1]} overlaps or has a raw exit")
        result.append({"kind": "ffn", "nodes": nodes,
                       "islands": ((motif[-1],),), "sink": motif[-1]})
        occupied.update(nodes)
    return sorted(result, key=lambda block: rank[block["nodes"][0]])
