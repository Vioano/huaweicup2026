"""Balanced Cartesian edge partitions and an explicitly restricted L1 order model.

No official evaluator, Task builder, spill model, or Cache simulator is imported.
The main DP is exact only for alternating column sweeps through consecutive
row bands, with prescribed q/q+1 contiguous quotas along the resulting word.
"""
from __future__ import annotations
from bisect import bisect_right
from collections import defaultdict
from itertools import accumulate
from typing import Sequence

Cell = tuple[int, int]


def _prefix(values: Sequence[int]) -> list[int]:
    return [0, *accumulate(values)]


def quotas(m: int, n: int, k: int) -> list[int]:
    if min(m, n, k) <= 0:
        raise ValueError("positive dimensions and core count required")
    q, r = divmod(m * n, k)
    return [q + int(c < r) for c in range(k)]


def coverage(parts: Sequence[Sequence[Cell]], a: Sequence[int], b: Sequence[int]):
    records = []
    for cells in parts:
        rows, cols = sorted({i for i, _ in cells}), sorted({j for _, j in cells})
        records.append(dict(cells=len(cells), rows=rows, columns=cols,
                            a_bytes=sum(a[i] for i in rows),
                            b_bytes=sum(b[j] for j in cols)))
    return records


def verify_partition(parts, m, n, k):
    flat = [cell for part in parts for cell in part]
    if len(flat) != m*n or len(set(flat)) != m*n:
        raise AssertionError("missing or duplicated cells")
    if set(flat) != {(i, j) for i in range(m) for j in range(n)}:
        raise AssertionError("invalid cell coordinates")
    if [len(p) for p in parts] != quotas(m,n,k):
        raise AssertionError("quota mismatch")


def _one_axis(a, b, k, first_direction=0, secondary_axis=0):
    """State = (completed rows x, next direction d, open-core B support width t).

    The global number x*n of visited cells determines the open core and its
    remaining quota. At a band boundary its column footprint is a prefix at
    the side where the next band starts; all earlier row costs are sunk.
    """
    m, n = len(a), len(b)
    caps = quotas(m,n,k); ends = [0, *accumulate(caps)]
    pa,pb = _prefix(a),_prefix(b)
    dp = [dict() for _ in range(m+1)]
    dp[0][(first_direction,0)] = (0,0,0)
    parent = {}
    states=transitions=0

    def col_cost(lo, hi, d):  # offsets in traversal direction, inclusive
        if d:
            lo,hi = n-1-hi,n-1-lo
        return pb[hi+1]-pb[lo]

    def row_cost(x,h,pos,length):
        if length >= h:
            return pa[x+h]-pa[x]
        lo=pos % h; stop=lo+length
        if stop <= h:
            return pa[x+stop]-pa[x+lo]
        return pa[x+h]-pa[x+lo]+pa[x+stop-h]-pa[x]

    for x in range(m):
        z=x*n; first=bisect_right(ends,z)-1; used=z-ends[first]
        for (d,t),value in sorted(dp[x].items()):
            states+=1
            for h in range(1,m-x+1):
                transitions+=1
                pos=0;c=first; ca=cb=0; nt=0
                while pos < h*n:
                    take=min(h*n-pos, ends[c+1]-z-pos)
                    if take<=0:
                        c+=1;continue
                    lo,hi=pos//h,(pos+take-1)//h
                    ca+=row_cost(x,h,pos,take)
                    if c==first and used:
                        assert lo==0 and t>0
                        if hi+1 > t:
                            cb+=col_cost(t,hi,d)
                    else:
                        cb+=col_cost(lo,hi,d)
                    pos+=take
                    nt=hi-lo+1 if z+pos < ends[c+1] else 0
                    if z+pos==ends[c+1]:c+=1
                secondary=ca if secondary_axis==0 else cb
                candidate=(value[0]+ca+cb,value[1]+secondary,value[2]+1)
                target=(1-d,nt)
                old=dp[x+h].get(target)
                if old is None or candidate < old:
                    dp[x+h][target]=candidate
                    parent[(x+h,*target)]=(x,d,t,h)
    last,value=min(dp[m].items(),key=lambda kv:(kv[1],kv[0]))
    x=m;d,t=last; bands=[]
    while x:
        px,pd,pt,h=parent[(x,d,t)]
        bands.append(h);x,d,t=px,pd,pt
    bands.reverse()
    order=[];x=0;d=first_direction
    for h in bands:
        cols=range(n) if d==0 else range(n-1,-1,-1)
        order.extend((i,j) for j in cols for i in range(x,x+h))
        x+=h;d=1-d
    parts=[order[ends[c]:ends[c+1]] for c in range(k)]
    verify_partition(parts,m,n,k)
    rec=coverage(parts,a,b)
    if value[0] != sum(r['a_bytes']+r['b_bytes'] for r in rec):
        raise AssertionError("DP recurrence and independently counted coverage differ")
    return dict(parts=parts,bands=bands,direction=first_direction,
                coverage_bytes=value[0],footprints=rec,
                states=states,transitions=transitions)


def construct_grid(a: Sequence[int], b: Sequence[int], k: int):
    """One deterministic output. Weighted groups are supported.

    Compare both band orientations and their reversals algebraically, and keep
    the two original plain-axis quota slices as controls. No E0 candidates are
    generated. Ties prefer less replication of the heavier mean-weight axis,
    then fewer bands, then fixed enumeration order.
    """
    a,b=list(a),list(b)
    if not a or not b or any(type(x) is not int or x<=0 for x in a+b):
        raise ValueError("nonempty positive integer group weights required")
    if type(k) is not int or not 1<=k<=5:
        raise ValueError("core count must be 1..5")
    m,n=len(a),len(b)
    heavy=0 if sum(a)*n>=sum(b)*m else 1
    candidates=[]
    stats=[]
    for axis in (0,1):
        aa,bb=(a,b) if axis==0 else (b,a)
        for direction in (0,1):
            sol=_one_axis(aa,bb,k,direction,heavy if axis==0 else 1-heavy)
            if axis:
                sol['parts']=[[(j,i) for i,j in p] for p in sol['parts']]
            sol['footprints']=coverage(sol['parts'],a,b)
            sol.update(axis=axis,family='alternating_band_quota')
            candidates.append(sol)
            stats.append(dict(axis=axis,direction=direction,
                              states=sol['states'],transitions=sol['transitions']))
        order=[(i,j) if axis==0 else (j,i)
               for i in range(len(aa)) for j in range(len(bb))]
        ends=[0,*accumulate(quotas(m,n,k))]
        ps=[order[ends[c]:ends[c+1]] for c in range(k)]
        rec=coverage(ps,a,b)
        candidates.append(dict(parts=ps,bands=[],axis=axis,direction=0,
                               family='plain_axis_control',footprints=rec,
                               coverage_bytes=sum(r['a_bytes']+r['b_bytes'] for r in rec)))
    def key(pair):
        index,sol=pair
        heavy_bytes=sum(r['a_bytes' if heavy==0 else 'b_bytes'] for r in sol['footprints'])
        return sol['coverage_bytes'],heavy_bytes,len(sol['bands']),index
    _,best=min(enumerate(candidates),key=key)
    verify_partition(best['parts'],m,n,k)
    best['dp_runs']=stats
    return best


def pair_cache_bytes(word: Sequence[Cell], a, b):
    """Atomic full-group model retaining only the current A and current B."""
    total=0;previous=None
    for i,j in word:
        if previous is None or previous[0]!=i:total+=a[i]
        if previous is None or previous[1]!=j:total+=b[j]
        previous=i,j
    return total


def row_block_word(cells: Sequence[Cell], a, b):
    """Optimal endpoint choices for fixed ascending A-block order, O(E) after sorting.

    This optimizes only the atomic two-group L1 model, NOT official Belady/Cache.
    The groups can have unequal B weights. Within each A-block every cell is used
    once. Candidate saving at an A transition is the retained B group's weight.
    """
    neighbors=defaultdict(list)
    for i,j in cells:neighbors[i].append(j)
    rows=sorted(neighbors)
    dp={None:0};history=[]
    for i in rows:
        js=sorted(neighbors[i]);nxt={};back={}
        base=max(dp,key=lambda z:(dp[z],-1 if z is None else -z))
        reuse=sorted(((dp[x]+b[x],x) for x in js if x in dp),
                     key=lambda z:(-z[0],z[1]))[:2]
        for exit_j in js:
            entry=(js[0] if len(js)==1 or js[0]!=exit_j else js[1])
            value=dp[base]
            pred=base
            if len(js)==1:
                if exit_j in dp and dp[exit_j]+b[exit_j]>value:
                    value=dp[exit_j]+b[exit_j];pred=entry=exit_j
            else:
                for score,x in reuse:
                    if x!=exit_j and score>value:
                        value=score;pred=entry=x
                        break
            nxt[exit_j]=value;back[exit_j]=(pred,entry)
        dp=nxt;history.append(back)
    if not rows:return [],0
    end=min(dp,key=lambda j:(-dp[j],j));saving=dp[end]
    blocks=[]
    for i,back in reversed(list(zip(rows,history))):
        prev,entry=back[end];js=sorted(neighbors[i])
        if len(js)==1:word=[js[0]]
        else:word=[entry]+[j for j in js if j not in {entry,end}]+[end]
        blocks.append([(i,j) for j in word]);end=prev
    ordered=[cell for block in reversed(blocks) for cell in block]
    expected=sum(a[i] for i in rows)+sum(b[j] for i,j in cells)-saving
    assert pair_cache_bytes(ordered,a,b)==expected
    assert set(ordered)==set(cells) and len(ordered)==len(cells)
    return ordered,expected


def support_hall_checks(parts,m,n):
    """Compatibility audit for the actual support sets, independent of edge labels.

    Allowed core set for (i,j) is {c: i in R_c and j in C_c}. Integer max-flow
    can assign all prescribed quotas iff its core-subset Hall inequalities hold.
    This routine checks those inequalities; it does not search for support sets.
    """
    k=len(parts);row=[{i for i,j in p} for p in parts];col=[{j for i,j in p} for p in parts]
    allowed=[sum(1<<c for c in range(k) if i in row[c] and j in col[c])
             for i in range(m) for j in range(n)]
    if any(mask==0 for mask in allowed):raise AssertionError('uncovered support cell')
    records=[]
    for mask in range(1,1<<k):
        demand=sum(len(parts[c]) for c in range(k) if mask>>c&1)
        supply=sum(bool(v & mask) for v in allowed)
        if supply<demand:raise AssertionError('Hall quota failure')
        records.append(dict(core_subset=mask,demand=demand,neighbor_cells=supply))
    return records
