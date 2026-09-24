"""Necessary projection-cover bound for balanced edges of a complete grid.

This bounds logical input replication, not physical DDR traffic or Makespan.
Support witnesses from the relaxation need not define a feasible partition.
"""


def lower_bound(rows, columns, row_bytes, column_bytes, edge_counts):
    if any(type(x) is not int or x <= 0 for x in (rows, columns, row_bytes, column_bytes)):
        raise ValueError("dimensions and input-group byte sizes must be positive integers")
    if any(type(e) is not int or e < 0 for e in edge_counts) or sum(edge_counts) != rows * columns:
        raise ValueError("edge counts must partition the complete grid")
    targets = (2 * rows, 2 * columns)
    states = {(0, 0): (0, ())}
    individual = 0
    for edges in edge_counts:
        options = [(0, 0)] if edges == 0 else [
            (r, s) for r in range(1, min(rows, edges) + 1)
            for s in range(1, min(columns, edges) + 1) if r * s >= edges]
        individual += min(row_bytes * r + column_bytes * s for r, s in options)
        updated = {}
        for (total_r, total_s), (cost, shapes) in states.items():
            for r, s in options:
                # Every row must either occur twice or be in a full-column support.
                key = (min(targets[0], total_r + r * (1 + (s == columns))),
                       min(targets[1], total_s + s * (1 + (r == rows))))
                candidate = (cost + row_bytes * r + column_bytes * s, shapes + ((r, s),))
                if key not in updated or candidate < updated[key]:
                    updated[key] = candidate
        states = updated
    value, witness = states[targets]
    return {"lower_bound_bytes": value, "individual_support_bound_bytes": individual,
            "relaxed_support_witness": [list(pair) for pair in witness],
            "scope": "necessary logical input-copy coverage bound; witness feasibility and Makespan are not certified"}
