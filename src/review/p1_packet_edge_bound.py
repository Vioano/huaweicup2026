"""Optimistic packet-box costs under the documented W-first tensor condition.

Exact arrangement minimization adapts archived Pro R4 src/edge_envelope.py.
The W-first fill bound is derived in P1_RETURN_CUT_RESOURCE_BOUND.md.
No graph compiler, response simulation, solver or evaluator is called here.
"""
from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from itertools import combinations


def exact_box_minimum(left, right, box):
    """Exact REAL minimum of max(left)+max(right), then an integer lower bound.

    Each affine is (q coefficient, s coefficient, constant). The region is
    the closed box clipped by s<=q. Arrangement vertices cover all linear cells.
    """
    if (len(box) != 4 or any(type(x) is not int for x in box) or
            not left or not right or any(len(f) != 3 or any(type(x) is not int for x in f)
                                        for f in (*left, *right))):
        raise ValueError('integer box and nonempty integer affine forms required')
    ql, qh, sl, sh = box
    if ql > qh or sl > sh or sl > qh:
        raise ValueError('empty clipped box')
    lines = [(1, 0, -ql), (1, 0, -qh), (0, 1, -sl), (0, 1, -sh), (1, -1, 0)]
    for forms in (left, right):
        for a, b in combinations(forms, 2):
            d = tuple(x - y for x, y in zip(a, b))
            if d[0] or d[1]:
                lines.append(d)
    points = set()
    for a, b in combinations(lines, 2):
        determinant = a[0] * b[1] - b[0] * a[1]
        if determinant:
            q = Fraction(a[1] * b[2] - b[1] * a[2], determinant)
            s = Fraction(a[2] * b[0] - b[2] * a[0], determinant)
            if ql <= q <= qh and sl <= s <= sh and s <= q:
                points.add((q, s))
    if not points:
        raise ValueError('no vertices in clipped box')
    def evaluate(forms, q, s):
        return max(a * q + b * s + c for a, b, c in forms)
    minimum, q, s = min((evaluate(left, q, s) + evaluate(right, q, s), q, s)
                        for q, s in points)
    return dict(real_minimum=str(minimum),
                integer_lower_bound=-(-minimum.numerator // minimum.denominator),
                witness=[str(q), str(s)], vertices_checked=len(points),
                left=list(left), right=list(right), box=list(box))


@dataclass(frozen=True)
class Resources:
    a: int
    b: int
    c: int
    d_prefix: int
    d_return: int
    d_whole: int
    counts: tuple[int, ...]
    gate: int

    def __post_init__(self):
        values = (self.a, self.b, self.c, self.d_prefix, self.d_return,
                  self.d_whole, self.gate, *self.counts)
        if not self.counts or any(type(v) is not int or v < 0 for v in values):
            raise ValueError('nonnegative integers and nonempty core counts required')
        if min(self.a, self.b, self.c) < 1 or self.d_prefix + self.d_return < self.d_whole:
            raise ValueError('invalid work or mandatory service')

    def forms(self, n, r, *, positive_s=False):
        if type(n) is not int or type(r) is not int or not 0 <= r <= n <= min(self.counts):
            raise ValueError('invalid packet state')
        k, a, b, c = len(self.counts), self.a, self.b, self.c
        span = a + b + c
        # W compute spines precede P/R under the explicit tensor condition.
        # For s>0, first P requires a cycles before any of its s*b V work.
        edge = ((span, -b-c, r*c),
                (span, -a-c, a if positive_s else 0),
                (k*self.d_whole, k*(self.d_prefix-self.d_whole), k*r*self.d_return))
        largest = max(self.counts) - n
        total = sum(self.counts) - k*n
        tail = ((-a-c, c, largest*(a+c)),
                (-b, 0, largest*b),
                (-k*self.d_whole, k*self.d_return, total*self.d_whole))
        return edge, tail

    def box(self, n, r, box, prefix_end=0):
        if type(prefix_end) is not int or prefix_end < 0:
            raise ValueError('nonnegative exact-model prefix cost required')
        if len(box) != 4 or any(type(v) is not int for v in box):
            raise ValueError('integer box required')
        if box[0] < 1 or box[1] > min(self.counts)-n or box[2] < 0:
            raise ValueError('box outside normal transitions')
        left, right = self.forms(n, r, positive_s=box[2] >= 1)
        answer = exact_box_minimum(left, right, box)
        answer.update(prefix_end=prefix_end, gate_before_edge=self.gate if n else 0,
                      frontier_lower_bound=prefix_end + (self.gate if n else 0)
                      + answer['integer_lower_bound'],
                      state=[n, r], scope='conditional exact-service packet class; NOT E0/global certificate')
        return answer
