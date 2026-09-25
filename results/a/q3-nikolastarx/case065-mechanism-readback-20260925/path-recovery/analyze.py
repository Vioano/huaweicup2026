"""Static readback of one frozen 065/K5 result; no solver imports."""
import gzip, hashlib, json, sys
from collections import defaultdict
from pathlib import Path

root = Path.cwd()
forest = Path(sys.argv[1])
snap = json.loads((root/'results/a/q3-nikolastarx/forest-current-headroom-20260925/cells-snapshot.json').read_text())
record, = [x['best'] for x in snap['cells'] if x['case_id']=='065' and x['cores']==5]
def get(name):
    ref=record['artifacts'][name]; p=forest/ref['path']; raw=p.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==ref['sha256'], name
    return json.loads(gzip.decompress(raw) if p.suffix=='.gz' else raw)
plan, result, trace, run = (get(x) for x in ('plan','result','trace','run'))
graph_path=root/'data/raw/a/official/data/case_065.json'
assert hashlib.sha256(graph_path.read_bytes()).hexdigest()==record['identity']['graph_sha256']
graph=json.loads(graph_path.read_text())
assert result['makespan']==record['metrics']['makespan_cycles']==trace['makespan']
out={'record_id':record['id'],'source_commit':record['solver_commit'],'identity':record['identity'],
     'artifacts':record['artifacts'],'result_makespan':result['makespan'],
     'task_count':result['task_count'],'task_dependencies':len(result['task_dependencies']),
     'cross_core_transfers':len(result['cross_core_transfers']),
     'data_movement_bytes':result['data_movement_bytes'],'cache_stats':result['cache_stats'],
     'core':[]}
for line in result['per_core_timeline']:
    ops=line['ops']; core=line['core_id']; bypipe=defaultdict(list)
    for op in ops: bypipe[op['pipe']].append(op)
    pipes={}
    for pipe, events in bypipe.items():
        events.sort(key=lambda x:(x['start'],x['end'],x['op_id']))
        gaps=[]; last=0
        for op in events:
            if op['start']>last: gaps.append({'from':last,'to':op['start'],'cycles':op['start']-last,'next_op':op['op_id'],'next_type':op['op']})
            last=max(last,op['end'])
        pipes[pipe]={'op_count':len(events),'busy_cycles':sum(x['duration'] for x in events),
                     'first_start':events[0]['start'],'last_end':last,
                     'largest_gaps':sorted(gaps,key=lambda x:-x['cycles'])[:3]}
    out['core'].append({'core':core,'task_end':line['tasks'][0]['end'],'step3':result['step3_by_core'][str(core)],
                        'pipes':pipes,'last_ops':sorted(ops,key=lambda x:x['end'])[-6:]})
(Path(__file__).parent/'readback.json').write_text(json.dumps(out,indent=2,ensure_ascii=False)+'\n')
