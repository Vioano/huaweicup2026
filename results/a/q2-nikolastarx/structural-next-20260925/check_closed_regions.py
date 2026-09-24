"""Independent set-based checks of the structural analysis, no evaluator."""
import importlib.util
from pathlib import Path
import random
from types import SimpleNamespace

path = Path(__file__).with_name('closed_regions.py')
spec = importlib.util.spec_from_file_location('closed_regions', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

for seed in range(100):
    rng = random.Random(seed)
    succ = {u: {v for v in range(u + 1, 12) if rng.random() < .22} for u in range(12)}
    parent, _ = module.tree(list(reversed(range(12))), succ)
    exact = {}
    for u in reversed(range(12)):
        common = set.intersection(*(exact[v] for v in succ[u])) if succ[u] else {None}
        exact[u] = common | {u}
    for u in range(12):
        ancestors, v = {u}, u
        while v is not None:
            v = parent[v]
            ancestors.add(v)
        assert ancestors == exact[u], (seed, u)

for external in (False, True):
    succ = {0: {1, 2}, 1: {3}, 2: {3}, 3: set(), 4: ({1} if external else set())}
    pred = {u: {v for v in succ if u in succ[v]} for u in succ}
    index = SimpleNamespace(order=[0, 4, 1, 2, 3], pred=pred, succ=succ,
                            ops={u: {'pipe': 'PIPE_V'} for u in succ}, duration=lambda u: 1)
    regions, _ = module.discover(index)
    assert bool(regions) == (not external)
print('1200 postdominator nodes and 2 boundary fixtures passed; evaluator calls=0')
