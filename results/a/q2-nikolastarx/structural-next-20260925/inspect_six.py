"""Read-only structural diagnosis of six existing P2 plans; zero evaluator calls."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
from src.q2_nikolastarx.dag_direct import DAGIndex
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.e2_plan_pairs import pinned

DATA = '60afc38b327680fbda0ff10182e3e05a01edd72d'
FEED = 'results/a/q2-nikolastarx/active-core-full500-20260925-s59/20260924T1910Z-s59ee/board-feed-500-with-runtime-notes.json'


def main():
    raw = subprocess.check_output(['git','show',f'{DATA}:{FEED}'], cwd=ROOT)
    assert hashlib.sha256(raw).hexdigest() == '0b850686966d1d7c1ce1a8babb1655051756b42f9a59d5c6f6becd6a87f2f99c'
    records = {(r['case_id'],r['cores']):r for r in json.loads(raw)['records']}
    out=[]
    for case in ['003','005','056','068','086','088']:
        r=records[case,5]
        graph_raw=(ROOT/f'data/raw/a/official/data/case_{case}.json').read_bytes()
        assert hashlib.sha256(graph_raw).hexdigest()==r['identity']['graph_sha256']
        graph=json.loads(graph_raw); index=DAGIndex(graph)
        plan=pinned({'commit':DATA,**r['artifacts']['plan']})
        truth=pinned({'commit':DATA,**r['artifacts']['result']})
        core_by_sg={sg:core for core,row in enumerate(plan['core_schedules']) for sg in row}
        owner={int(u):core_by_sg[sg] for u,sg in plan['node_to_subgraph'].items()}
        giant=set(max(index.components,key=len))
        level={}; widths=Counter(); pipe_work=Counter(); core_work=defaultdict(Counter)
        for u in index.order:
            level[u]=1+max((level[v] for v in index.pred[u]),default=-1)
            if u in giant:
                widths[level[u]]+=1
                pipe_work[index.ops[u]['pipe']]+=index.duration(u)
                core_work[owner[u]][index.ops[u]['pipe']]+=index.duration(u)
        strict=[]
        for u in giant:
            if len(index.succ[u])!=2:continue
            a,b=sorted(index.succ[u])
            if index.pred[a]!={u} or index.pred[b]!={u}:continue
            if len(index.succ[a])!=1 or index.succ[a]!=index.succ[b]:continue
            j=next(iter(index.succ[a]))
            if index.pred[j]!={a,b}:continue
            if len({index.ops[v]['pipe'] for v in [u,a,b,j]})==1:strict.append([u,a,b,j])
        work=mandatory_copy_work(graph,plan,truth['bandwidth_bytes_per_cycle'])
        assert work['transfer_bytes']==truth['data_movement_bytes']['scheduled_copy_bytes']-truth['data_movement_bytes']['spill_added_copy_bytes']
        out.append({'case':case,'plan':r['artifacts']['plan'],'graph_sha256':r['identity']['graph_sha256'],
                    'compute_ops':len(index.ops),'components':len(index.components),
                    'giant_ops':len(giant),'giant_max_topological_layer_width':max(widths.values()),
                    'giant_pipe_work':dict(pipe_work),'giant_core_pipe_work':dict(core_work),
                    'giant_active_cores':len(core_work),
                    'cross_contracted_precedence_edges':sum(owner[u]!=owner[v] for u in index.ops for v in index.succ[u]),
                    'strict_same_pipe_single_op_diamonds':len(strict),'mandatory_copy':work,
                    'existing_E0_M':truth['makespan'],
                    'interpretation_limit':'Layer width is structural, not a feasible capacity-aware concurrency certificate. No macro-region coverage has been checked.'})
    report={'data_commit':DATA,'calls':{'solver':0,'Step1':0,'Step2':0,'Step3':0,'E0':0,'E1':0,'E2':0},
            'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'rows':out}
    Path(__file__).with_name('summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ['case','giant_ops','giant_active_cores','giant_max_topological_layer_width','strict_same_pipe_single_op_diamonds','existing_E0_M']} for r in out],indent=2))


if __name__=='__main__':main()
