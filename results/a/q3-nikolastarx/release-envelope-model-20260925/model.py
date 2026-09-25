"""Max-plus signatures of a fixed-service input FIFO feeding a serial chain.

This is a conditional mathematical model, not an official evaluator or E2.
Transfer service/release constraints cannot change with the candidate, and
allocation or internal-compute release dependencies are excluded.
"""
from collections import defaultdict


def signature(work, compute_before_use, release_keys, total_compute):
    """O(n) signature F(R)=max(base, max_key(R[key]+lag[key])).

    None release keys are ready at zero. Repeated labels share a release time.
    Compute-use positions need not follow FIFO order. All times are integer
    units of this fixed-service model; arbitrary fair-sharing events are absent.
    """
    n = len(work)
    if (len(compute_before_use) != n or len(release_keys) != n
            or type(total_compute) is not int or total_compute < 0
            or any(type(w) is not int or w <= 0 for w in work)
            or any(type(p) is not int or not 0 <= p <= total_compute
                   for p in compute_before_use)
            or any(k is not None and (not isinstance(k, str) or not k)
                   for k in release_keys)):
        raise ValueError('invalid fixed-service FIFO/chain')
    if not n:
        return {'base':total_compute,'lags':{}}
    sums = [0]
    for w in work:
        sums.append(sums[-1]+w)
    suffix = [None]*n
    for i in range(n-1,-1,-1):
        v = sums[i+1]-compute_before_use[i]
        suffix[i] = v if i==n-1 else max(v,suffix[i+1])
    base = total_compute+max(0,suffix[0])
    lags = {}
    for i,key in enumerate(release_keys):
        if key is not None:
            lag = total_compute-sums[i]+suffix[i]
            lags[key] = max(lags.get(key,lag),lag)
    # Canonical intercept = completion with every variable release at zero.
    base = max([base,*lags.values()])
    return {'base':base,'lags':lags}


def value(sig, releases):
    if set(releases) != set(sig['lags']) or any(type(v) is not int or v<0 for v in releases.values()):
        raise ValueError('provide exactly the nonnegative external releases')
    return max([sig['base'],*(releases[k]+lag for k,lag in sig['lags'].items())])


def uniformly_no_slower(a,b):
    """Exact iff test for F_a(R)<=F_b(R) for all independent R>=0.

    Requires identical release labels. It is not an official dominance test:
    real candidate changes can change services, cache, allocation and releases.
    """
    if set(a['lags']) != set(b['lags']):
        raise ValueError('release domains differ')
    return a['base']<=b['base'] and all(a['lags'][k]<=b['lags'][k] for k in a['lags'])


def direct(work, uses, keys, compute, releases):
    """Independent scalar FIFO and chain-event recurrence, for model tests."""
    ready_by_position = defaultdict(int)
    clock=0
    for w,p,k in zip(work,uses,keys):
        clock=max(clock,0 if k is None else releases[k])+w
        ready_by_position[p]=max(ready_by_position[p],clock)
    clock=spent=0
    for p,ready in sorted(ready_by_position.items()):
        clock=max(clock+p-spent,ready)
        spent=p
    return clock+compute-spent
