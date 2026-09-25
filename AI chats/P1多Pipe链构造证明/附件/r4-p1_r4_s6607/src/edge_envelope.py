"""Certified optimistic edge-box bounds, NOT a scheduling response model.

Requires private identical M(a)->V*(b)->M(c) chains and the complete-chain
M-obstruction premise stated in README. dP/dR/dW are exact per-fragment sums of
per-COPY rounded exclusive service. No MEM/FIFO response is fabricated here.

The complete lazy search controller is pseudocode in README; this module
implements the exact arithmetic subproblem used by each unexpanded box.
"""
from __future__ import annotations
from dataclasses import dataclass
from fractions import Fraction as F
from itertools import combinations
from typing import Sequence

Affine = tuple[int, int, int]  # A*q + B*s + C
Box = tuple[int, int, int, int]  # qlo, qhi, slo, shi; additionally s<=q


def value(a: Affine, q: F, s: F) -> F:
    return a[0] * q + a[1] * s + a[2]


def ceil(x: F) -> int:
    return -(-x.numerator // x.denominator)


def exact_box_minimum(left: Sequence[Affine], right: Sequence[Affine], box: Box) -> dict:
    """Minimize max(left)+max(right) over a REAL clipped box, exactly.

    The verifier must re-enumerate all arrangement vertices. An isolated
    feasible minimizer witness is not, by itself, a lower-bound certificate.
    At integer q,s all affine forms here are integral, so ceil(real minimum)
    is a valid lower bound over integer feasible transitions.
    """
    ql,qh,sl,sh=box
    if not left or not right or ql>qh or sl>sh or sl>qh:
        raise ValueError('empty forms or box')
    lines=[(1,0,-ql),(1,0,-qh),(0,1,-sl),(0,1,-sh),(1,-1,0)]
    for forms in (left,right):
        for a,b in combinations(forms,2):
            d=tuple(x-y for x,y in zip(a,b))
            if d[0] or d[1]:lines.append(d)
    points=set()
    for a,b in combinations(lines,2):
        det=a[0]*b[1]-b[0]*a[1]
        if det==0:continue
        q=F(a[1]*b[2]-b[1]*a[2],det)
        s=F(a[2]*b[0]-b[2]*a[0],det)
        if ql<=q<=qh and sl<=s<=sh and s<=q:points.add((q,s))
    if not points:raise ValueError('empty clipped region')
    records=[(max(value(a,q,s) for a in left)+max(value(a,q,s) for a in right),q,s)
             for q,s in points]
    minimum,q,s=min(records)
    return dict(real_minimum=str(minimum),integer_lower_bound=ceil(minimum),
                witness=[str(q),str(s)],vertices_checked=len(points),
                left=list(left),right=list(right),box=list(box))


@dataclass(frozen=True)
class Resources:
    a: int
    b: int
    c: int
    dP: int
    dR: int
    dW: int
    per_core_chain_counts: tuple[int,...]
    gate: int

    def __post_init__(self):
        if not self.per_core_chain_counts or min(self.per_core_chain_counts)<0:
            raise ValueError('invalid chain counts')
        if min(self.a,self.b,self.c)<1 or min(self.dP,self.dR,self.dW,self.gate)<0:
            raise ValueError('invalid resources')
        if self.dP+self.dR<self.dW:
            raise ValueError('fragment services inconsistent with mandatory whole-chain IO')

    def forms(self,n:int,r:int) -> tuple[tuple[Affine,...],tuple[Affine,...]]:
        K=len(self.per_core_chain_counts)
        if not 0<=r<=n<=min(self.per_core_chain_counts):raise ValueError('invalid state')
        # Complete-chain M obstruction, V work, total global DDR service.
        edge=((self.a+self.b+self.c,-self.b-self.c,self.c*r),
              (self.b,0,0),
              (K*self.dW,K*(self.dP-self.dW),K*r*self.dR))
        mmax=max(self.per_core_chain_counts)-n
        msum=sum(self.per_core_chain_counts)-K*n
        # Suffix bound at state (n+q,s), includes final unequal remainders.
        tail=((-self.a-self.c,self.c,mmax*(self.a+self.c)),
              (-self.b,0,mmax*self.b),
              (-K*self.dW,K*self.dR,msum*self.dW))
        return edge,tail

    def box(self,n:int,r:int,box:Box,prefix_end:int=0) -> dict:
        if box[0]<1 or box[1]>min(self.per_core_chain_counts)-n or box[2]<0:
            raise ValueError('box outside normal-transition domain')
        edge,tail=self.forms(n,r)
        certificate=exact_box_minimum(edge,tail,box)
        certificate['prefix_end']=prefix_end
        certificate['gate_before_edge']=self.gate if n else 0
        certificate['frontier_lower_bound']=(prefix_end+(self.gate if n else 0)
                                             +certificate['integer_lower_bound'])
        certificate['state']=[n,r]
        return certificate
