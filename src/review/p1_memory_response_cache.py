"""Opt-in, process-local research cache for the restricted P1 Family domain.

This does not integrate with a solver. See docs/a/P1_MEMORY_KEY_SOURCE_PROOF.md.
Only a successfully compiled representative can seed a key; hits rely on the
explicit domain contract, whose independent review is still pending.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib

from src.q1.response_oracle import PortOp, Task
from src.review.p1_memory_key_contract import (
    assert_compute_incidence, release_word, source_scope,
)


@dataclass(frozen=True)
class DomainContract:
    kind: str
    reviewed: bool


class MemoryResponseCache:
    """Cache normalized Task/traffic by (Family.prekey, R4 release word).

    ``compiler(nodes)`` must return ``(Task, traffic, prepared_step3_task)``.
    It must execute the real frozen builder in production research use. The
    adapter is injectable solely for pure contract tests.
    """

    DOMAIN = "ordered-private-official-builder-actual-incidence-v1"

    def __init__(self, family, *, domain_contract, compiler, max_task_compiles):
        if not isinstance(domain_contract, DomainContract) or (
                domain_contract.kind != self.DOMAIN or domain_contract.reviewed is not True):
            raise ValueError("explicit reviewed ordered-private domain contract required")
        certificate = family.family_certificate
        if certificate.get("private") is not True or certificate.get("original_ids_unchanged") is not True:
            raise ValueError("Family lacks ordered private original-ID certificate")
        if not callable(compiler) or type(max_task_compiles) is not int or max_task_compiles < 1:
            raise ValueError("compiler and positive Task compile budget required")
        self.family = family
        self.compiler = compiler
        self.limit = max_task_compiles
        self.scope = source_scope(family.capacity, family.bandwidth)
        self.entries = {}
        self.compile_attempts = 0
        self.compiles_confirmed = 0
        self.hits = 0
        self.misses = 0
        self.requests = []

    def _check_scope(self):
        if self.scope != source_scope(self.family.capacity, self.family.bandwidth):
            raise ValueError("official/helper/config/runtime/capacity/bandwidth source drift")

    @staticmethod
    def _normalized(task):
        if not isinstance(task, Task):
            raise TypeError("compiler must return a Task")
        # IDs in a representative belong only to diagnostics. A hit returns
        # no actual op/task IDs; a final plan must compile its real Tasks again.
        return Task(tuple(tuple(PortOp(op.work, op.ddr, op.need, -1)
                                for op in port) for port in task.ports), -1)

    def get(self, nodes):
        self._check_scope()  # including hits; never use a cache after drift
        nodes = tuple(nodes)
        if not nodes or len(nodes) != len(set(nodes)) or not set(nodes) <= self.family.eligible:
            raise ValueError("nodes must be a nonempty distinct compute subset of this Family")
        key = (self.family.prekey(nodes), release_word(self.family.view, nodes))
        digest = hashlib.sha256(repr(key).encode()).hexdigest()
        if key in self.entries:
            self.hits += 1
            row = self.entries[key]
            self.requests.append({"hit": True, "actual_nodes": nodes, "key_digest": digest})
            return {"task": row["task"], "traffic": deepcopy(row["traffic"]),
                    "actual_nodes": nodes, "key_digest": digest, "cache_hit": True}
        if self.compile_attempts >= self.limit:
            raise RuntimeError("Task compile budget exhausted before compiler call")
        self.misses += 1
        self.compile_attempts += 1  # counts an attempted call even if it fails
        self.requests.append({"hit": False, "actual_nodes": nodes, "key_digest": digest})
        task, traffic, prepared = self.compiler(nodes)
        self.compiles_confirmed += 1
        self._check_scope()
        if traffic.get("spill_added_copy_bytes") != 0:
            raise ValueError("representative inserted spill traffic")
        if prepared.get("step3", {}).get("execution_contract_validated") is not True:
            raise ValueError("representative Step3 execution contract not validated")
        assert_compute_incidence(self.family.view, nodes, prepared)
        normalized = self._normalized(task)
        row = {"task": normalized, "traffic": deepcopy(traffic),
               "representative_nodes": nodes}
        self.entries[key] = row
        return {"task": normalized, "traffic": deepcopy(row["traffic"]),
                "actual_nodes": nodes, "key_digest": digest, "cache_hit": False}
