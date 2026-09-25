from __future__ import annotations
import json
from itertools import accumulate, product, permutations
from pathlib import Path
from grid_band_dp import (construct_grid, coverage, quotas, pair_cache_bytes,
                          row_block_word, support_hall_checks, _one_axis)

HERE=Path(__file__).resolve().parent

def plain(m,n,k):
    order=[(i,j) for i in range(m) for j in range(n)]
    ends=[0,*accumulate(quotas(m,n,k))]
    return [order[ends[c]:ends[c+1]] for c in range(k)]

records=[]
for label,m,n,a,b,lower in [('m17_n15',17,15,270336,135168,14868480),
                             ('m18_n16',18,16,202752,135168,13246464)]:
    aa=[a]*m;bb=[b]*n
    sol=construct_grid(aa,bb,5)
    old=plain(m,n,5)
    pair_new=[];pair_old=[];star_words=[]
    for cells in sol['parts']:
        word,cost=row_block_word(cells,aa,bb)
        pair_new.append(cost);star_words.append(word)
        r=len({i for i,j in cells})
        universal=a*r+b*(len(cells)-r+1)
        assert cost==universal
    for cells in old:
        _,cost=row_block_word(cells,aa,bb);pair_old.append(cost)
    matrix=[[-1]*n for _ in range(m)]
    for c,cells in enumerate(sol['parts']):
        for i,j in cells:matrix[i][j]=c
    entry=dict(parameter_label=label,scope='abstract complete Cartesian edge partition; no raw case graph read',
               m=m,n=n,cores=5,a_bytes=a,b_bytes=b,
               lower_bound_for_all_balanced_edge_partitions=lower,
               solution=sol,owner_matrix=matrix,
               row_block_words=star_words,
               pair_cache_model_new_bytes=sum(pair_new),
               pair_cache_model_plain_axis_bytes=sum(pair_old),
               pair_cache_model_scope='sequential whole trees; full atomic groups; only current A/B retained; no official trace',
               hall_checks=support_hall_checks(sol['parts'],m,n),
               official_evaluator_calls=0)
    records.append(entry)

# Independently enumerate tiny BAND compositions, not edge assignments.
checks=0
for m,n,k in [(2,3,2),(3,4,3),(4,3,3),(5,3,4)]:
    aa=[2+i%3 for i in range(m)];bb=[1+j%2 for j in range(n)]
    for d in (0,1):
        result=_one_axis(aa,bb,k,d)
        best=None
        for split_bits in product((0,1),repeat=m-1):
            boundaries=[0]+[i+1 for i,x in enumerate(split_bits) if x]+[m]
            hs=[v-u for u,v in zip(boundaries,boundaries[1:])]
            word=[];x=0
            for p,h in enumerate(hs):
                dd=(d+p)%2
                columns=range(n) if not dd else range(n-1,-1,-1)
                word.extend((i,j) for j in columns for i in range(x,x+h));x+=h
            ends=[0,*accumulate(quotas(m,n,k))]
            parts=[word[ends[c]:ends[c+1]] for c in range(k)]
            rec=coverage(parts,aa,bb)
            value=sum(r['a_bytes']+r['b_bytes'] for r in rec)
            best=value if best is None else min(best,value)
        assert result['coverage_bytes']==best
        checks+=1

# Endpoint DP checked against every within-row permutation for this tiny family.
a=[5,7,6];b=[2,3,4]
for cells in [[(i,j) for i in range(3) for j in range(3)],
              [(0,0),(0,2),(1,1),(1,2),(2,0),(2,1)],
              [(0,0),(1,0),(1,1),(2,1)]]:
    w,value=row_block_word(cells,a,b)
    rows=sorted({i for i,j in cells})
    options=[list(permutations([j for ii,j in cells if ii==i])) for i in rows]
    brute=min(pair_cache_bytes([(i,j) for i,js in zip(rows,chosen) for j in js],a,b)
              for chosen in product(*options))
    assert value==brute
    checks+=1

out=dict(records=records,small_restricted_model_checks=checks,
         all_small_checks_passed=True,official_evaluator_calls=0,
         inputs='user-supplied abstract parameters and invented tiny weighted grids only')
(HERE/'certificates.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for rec in records:
    sol=rec['solution']
    print(rec['parameter_label'],sol['coverage_bytes'],sol['bands'],sol['axis'],sol['direction'],
          [(len(x['rows']),len(x['columns'])) for x in sol['footprints']],
          rec['pair_cache_model_new_bytes'],rec['pair_cache_model_plain_axis_bytes'])
print('restricted small checks',checks)
