"""Pre-registered selection: raw ops only; does not read results or invoke solvers."""
import argparse, hashlib, json
from pathlib import Path
SALT = 'p2-15d-k5-holdout-v1'
EXCLUDED = ['005','010','064','068','069','071','086','088']
def selection(raw):
    rows=[]
    for i in range(1,101):
        case=f'{i:03d}'
        if case in EXCLUDED: continue
        data=(raw/'data'/f'case_{case}.json').read_bytes()
        graph=json.loads(data)
        assert isinstance(graph['ops'],list)
        rows.append(dict(case=case, node_count=len(graph['ops']), graph_sha256=hashlib.sha256(data).hexdigest(), selection_key=hashlib.sha256((SALT+case).encode('utf-8')).hexdigest()))
    rows.sort(key=lambda r:(r['node_count'],r['case']))
    strata=[]; chosen=[]
    for q in range(4):
        group=rows[q*23:(q+1)*23]
        ranked=sorted(group,key=lambda r:(r['selection_key'],r['case']))
        ids=[r['case'] for r in ranked[:3]]
        strata.append(dict(quartile=q+1,node_count_min=group[0]['node_count'],node_count_max=group[-1]['node_count'],members=group,selected=ids))
        chosen.extend(ids)
    return dict(schema='p2-holdout12-selection-v1',salt=SALT,excluded_cases=EXCLUDED,selection_rule='Exclude eight prior reverse probes. Sort remaining 92 by (len(original JSON ops), three-digit case_id); four consecutive groups of 23, ties by case_id. Within each sort SHA256(UTF8(salt + three-digit case_id)), no separator, then case_id; select first three. Dispatch order is strata 1..4, then within-stratum hash order.',node_count_definition='len(raw JSON ops), including original COPY nodes; no prepared graph or performance information',coordinates=[[c,5] for c in chosen],strata=strata,scoring_calls=0)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--raw-root',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=selection(a.raw_root)
    with a.output.open('x') as f: json.dump(result,f,indent=2,ensure_ascii=False);f.write('\n')
    print(json.dumps({'coordinates':result['coordinates'],'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest()}))
