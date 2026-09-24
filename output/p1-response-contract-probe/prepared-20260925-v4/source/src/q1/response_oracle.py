"""Exact-rational research response for four FIFO pipes and shared DDR.

This models integer operation retirement with fluid DDR service. It is NOT
certified equivalent to official binary64/EPS arithmetic. The compiled input
must have no cross-core dependency, spill or hidden memory constraint.
The synchronous quotient is exact within this mathematical model only.

Design source: archived P1 Pro R2, assistant 0380bf48-1f2b-4167-87f5-5e31814adff6,
commit d6e640a337001e333108f592e6876ac6bd0a2561. Original archives are unmodified.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from typing import Sequence

PIPES = ("PIPE_M", "PIPE_V", "PIPE_MTE2", "PIPE_MTE3")


@dataclass(frozen=True)
class PortOp:
    work: int
    ddr: bool
    need: tuple[int, int, int, int]
    original_id: int = -1


@dataclass(frozen=True)
class Task:
    ports: tuple[tuple[PortOp, ...], ...]
    task_id: int = -1

    def signature(self):
        return tuple(tuple((op.work, op.ddr, op.need) for op in port)
                     for port in self.ports)

    def scaled_ddr(self, multiplicity: int):
        if type(multiplicity) is not int or multiplicity < 1:
            raise ValueError("multiplicity must be a positive integer")
        return Task(tuple(tuple(replace(op, work=op.work * multiplicity)
                                if op.ddr else op for op in port)
                          for port in self.ports), self.task_id)


def _validate(lines, gate, max_events):
    if type(gate) is not int or gate < 0:
        raise ValueError("gate must be a nonnegative integer")
    if type(max_events) is not int or max_events < 1:
        raise ValueError("max_events must be positive")
    for line in lines:
        for task in line:
            if len(task.ports) != 4 or not any(task.ports):
                raise ValueError("a Task needs four ports and at least one operation")
            for p, port in enumerate(task.ports):
                for rank, op in enumerate(port):
                    if type(op.work) is not int or op.work < 1 or type(op.ddr) is not bool:
                        raise ValueError("operation work must be positive integer; ddr boolean")
                    if len(op.need) != 4 or any(type(n) is not int or n < 0 or
                                              n > len(task.ports[q])
                                              for q, n in enumerate(op.need)):
                        raise ValueError("invalid completed-prefix requirement")
                    if op.need[p] > rank:
                        raise ValueError("operation requires itself or a later FIFO operation")


def simulate(lines: Sequence[Sequence[Task]], gate: int = 100, *,
             keep_trace: bool = False, max_events: int = 2_000_000):
    """Simulate one declared mathematical model, never invoke an evaluator.

    `service_cycles` sums unshared COPY durations, not transferred bytes.
    `ddr_retirement_union` includes the integer retirement rounding interval.
    Deadlock/event-budget exhaustion is an explicit error, never a score.
    """
    _validate(lines, gate, max_events)
    cores = len(lines)
    index = [0] * cores
    done = [[0] * 4 for _ in lines]
    active = [False] * cores
    release = [0] * cores
    finishes = [0] * cores
    starts = [0] * cores
    busy = [[None] * 4 for _ in lines]
    remaining: dict[tuple[int, int], Fraction] = {}
    now = events = service = ddr_union = 0
    trace, intervals = [], []
    while True:
        events += 1
        if events > max_events:
            raise RuntimeError("response event budget exhausted")
        # Retire all completions before activating/issuing at this integer time.
        for c in range(cores):
            for p, slot in enumerate(busy[c]):
                if slot is None:
                    continue
                op, start, end = slot
                completed = remaining[c, p] == 0 if op.ddr else end <= now
                if completed:
                    busy[c][p] = None
                    done[c][p] += 1
                    if op.ddr:
                        del remaining[c, p]
                    if keep_trace:
                        trace.append(dict(core=c, task=lines[c][index[c]].task_id,
                                          pipe=PIPES[p], op_id=op.original_id,
                                          start=start, end=now, ddr=op.ddr,
                                          work=op.work))
            if active[c] and all(done[c][p] == len(lines[c][index[c]].ports[p])
                                 for p in range(4)):
                intervals.append(dict(core=c, task=lines[c][index[c]].task_id,
                                      start=starts[c], end=now))
                finishes[c] = now
                index[c] += 1
                active[c] = False
                release[c] = now + gate
        if all(index[c] == len(lines[c]) for c in range(cores)):
            break
        for c in range(cores):
            if not active[c] and index[c] < len(lines[c]) and release[c] <= now:
                active[c] = True
                done[c] = [0] * 4
                starts[c] = now
            if not active[c]:
                continue
            for p, port in enumerate(lines[c][index[c]].ports):
                if busy[c][p] is not None or done[c][p] == len(port):
                    continue
                op = port[done[c][p]]
                if any(done[c][q] < n for q, n in enumerate(op.need)):
                    continue
                busy[c][p] = (op, now, None if op.ddr else now + op.work)
                if op.ddr:
                    remaining[c, p] = Fraction(op.work)
                    service += op.work
        next_times = [release[c] for c in range(cores)
                      if not active[c] and index[c] < len(lines[c]) and release[c] > now]
        next_times.extend(slot[2] for slots in busy for slot in slots
                          if slot is not None and not slot[0].ddr)
        if remaining:
            fluid_delta = min(remaining.values()) * len(remaining)
            next_times.append(now + (-(-fluid_delta.numerator // fluid_delta.denominator)))
        if not next_times:
            raise ValueError("FIFO/dependency deadlock in response input")
        next_time = min(next_times)
        if next_time <= now:
            raise RuntimeError("response failed to advance")
        elapsed = Fraction(next_time - now)
        if remaining:
            ddr_union += next_time - now
        # Redistribution is continuous even when completion is sub-cycle.
        while elapsed:
            positive = [key for key, work in remaining.items() if work > 0]
            if not positive:
                break
            fluid_delta = min(remaining[key] for key in positive) * len(positive)
            amount = min(fluid_delta, elapsed)
            for key in positive:
                remaining[key] -= amount / len(positive)
            elapsed -= amount
        now = next_time
    result = dict(kind="rational_response_NOT_E0", makespan=now,
                  per_core_finish=finishes, events=events, service_cycles=service,
                  ddr_retirement_union=ddr_union, task_intervals=intervals)
    if keep_trace:
        result["trace"] = trace
    return result


def quotient(lines: Sequence[Sequence[Task]], gate: int = 100, *,
             max_events: int = 2_000_000):
    """Fold common synchronous rounds; the entire first divergent tail stays explicit.

    A core which is idle from the beginning prevents round folding. No padding,
    cross-core barrier or rounded byte aggregation is inserted to create symmetry.
    """
    _validate(lines, gate, max_events)
    cores = len(lines)
    count = total = 0
    cache, rounds = {}, []
    while count < min(map(len, lines), default=0):
        signatures = [line[count].signature() for line in lines]
        if any(sig != signatures[0] for sig in signatures[1:]):
            break
        sig = signatures[0]
        if sig not in cache:
            cache[sig] = simulate([[lines[0][count].scaled_ddr(cores)]], gate,
                                  max_events=max_events)
        cost = cache[sig]["makespan"]
        total += gate if count else 0
        rounds.append(dict(round=count, start=total, end=total + cost))
        total += cost
        count += 1
    tail = [line[count:] for line in lines]
    tail_result = None
    if any(tail):
        tail_result = simulate(tail, gate, max_events=max_events)
        total += (gate if count else 0) + tail_result["makespan"]
    return dict(kind="synchronous_quotient_NOT_E0", makespan=total,
                equal_rounds=count, distinct_responses=len(cache), rounds=rounds,
                explicit_tail_tasks=sum(map(len, tail)), tail=tail_result)
