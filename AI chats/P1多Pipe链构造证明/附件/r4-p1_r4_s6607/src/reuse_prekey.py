"""Conservative extension of Family.prekey for the frozen no-spill P1 compiler.

Pure metadata construction: no compiler/model/evaluator call. For persistent
caches, `scope` must bind exact compiler files, configuration and runtime.
The official builder emits compute tensor incidence in ascending tensor ID.
DO NOT sort the resulting set traversal: it is exactly the behavior being kept.
"""
from __future__ import annotations
import platform
import sys
from typing import Iterable


def runtime_scope() -> tuple:
    return (platform.python_implementation(), tuple(sys.version_info[:3]),
            sys.implementation.cache_tag, sys.maxsize,
            tuple(sys.hash_info))


def release_word(view, nodes: Iterable[int]) -> tuple:
    ns = set(nodes)
    tids = sorted(set().union(*(view.in_t[u] | view.out_t[u] for u in ns))) if ns else []
    rank = {t: i for i, t in enumerate(tids)}
    return tuple((tuple(rank[t] for t in set(sorted(view.in_t[u]))),
                  tuple(rank[t] for t in set(sorted(view.out_t[u]))))
                 for u in sorted(ns))


def memory_prekey(family, nodes: Iterable[int], scope: tuple) -> tuple:
    nodes = tuple(nodes)
    return scope, runtime_scope(), family.prekey(nodes), release_word(family.view, nodes)
