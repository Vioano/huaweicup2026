"""Summarize stored official Cache/compute timelines; zero evaluator calls."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path


def summarize(path):
    raw = path.read_bytes()
    result = json.loads(gzip.decompress(raw) if path.suffix == '.gz' else raw)
    events = result.get('cache_events', [])
    per_core = []
    for core in result['per_core_timeline']:
        pipes = {}
        for pipe in ('PIPE_M', 'PIPE_V'):
            ops = sorted((op for op in core['ops'] if op['pipe'] == pipe),
                         key=lambda op: (op['start'], op['op_id']))
            work = sum(op['duration'] for op in ops)
            end = max((op['end'] for op in ops), default=0)
            pipes[pipe] = dict(work_cycles=work, finish=end,
                               idle_before_finish=end - work,
                               last_op_id=ops[-1]['op_id'] if ops else None)
        per_core.append(dict(core_id=core['core_id'], pipes=pipes,
                             finish=max(op['end'] for op in core['ops'])))
    return dict(path=path.as_posix(), sha256=hashlib.sha256(raw).hexdigest(),
                makespan_cycles=result['makespan'], movement=result['data_movement_bytes'],
                cache_stats=result.get('cache_stats'),
                cache_event_counts=dict(Counter(event['event'] for event in events)),
                evicted_entries=sum(len(event.get('evicted_tensor_ids', [])) for event in events),
                per_core=per_core)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('manifest', type=Path)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    m = json.loads(args.manifest.read_text(encoding='utf-8'))
    items = []
    for e in m['evaluations']:
        if e['problem'] != 'P3':
            continue
        row = summarize(Path(e['artifacts']['result']['path']))
        row.update(case_id=e['case_id'], variant=e['variant'])
        items.append(row)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(dict(
        note='Derived from complete stored E0 results; zero new solver/evaluator calls. '
             'Compute idle is a timeline statistic, not a proven attribution of delay.',
        input_manifest=args.manifest.as_posix(), rows=items), indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
