"""Export all 500 P1 winners from a fixed, previously audited signed snapshot."""
import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from audit import expected_cells, require, verify_snapshot

def export(report_path,payload_dir,output):
    report=json.loads(report_path.read_bytes());require(report['status']=='passed','Snapshot audit must pass first')
    manifest=report['snapshot'];payload=verify_snapshot(manifest,(payload_dir/manifest['payload_file']).read_bytes())
    cells=[c for c in expected_cells(payload) if c['problem']=='P1']
    require(len(cells)==500 and len({(c['case_id'],c['cores']) for c in cells})==500,'P1 coverage differs')
    rows=[]
    for cell in cells:
        r=cell['best'];require(r and r['eligible'] and r['baseline_verified'],'P1 cell is not admitted with a verified denominator')
        m=r['metrics'];source=r['source']
        rows.append(dict(case_id=cell['case_id'],cores=cell['cores'],makespan_cycles=m['makespan_cycles'],
            baseline_speedup=m['baseline_speedup'],extra_ddr_bytes=m.get('extra_ddr_bytes'),
            solver_wall_seconds=m.get('solver_wall_seconds'),evaluation_wall_seconds=m.get('evaluation_wall_seconds'),
            algorithm_id=r['algorithm_id'],run_id=r['run_id'],attempt_id=r['attempt_id'],revision=r['revision'],
            record_id=r['id'],solver_commit=r['solver_commit'],source_commit=source['commit'],source_url=source['url']))
    summary=dict(snapshot_id=payload['snapshot_id'],snapshot_records=len(payload['records']),
        scope='Current admitted historical-best portfolio across algorithms, not one solver or a fresh E0 run.',
        aggregation='Arithmetic mean of each of the 100 case baseline_speedup ratios per core count; not a ratio of summed Makespan.',
        timing='Per-row solver and external evaluation wall times are retained separately; they are not the cost of constructing this portfolio.',
        new_solver_calls=0,new_evaluation_calls=0,cores={})
    for k in range(1,6):
        selected=[r for r in rows if r['cores']==k];values=[r['baseline_speedup'] for r in selected]
        average=sum(values)/len(values)
        require(len(selected)==100 and math.isclose(average,report['checks']['means']['P1'][str(k)]['mean'],rel_tol=1e-14),'P1 means differ from audited report')
        summary['cores'][str(k)]=dict(count=100,mean_speedup=average,min_speedup=min(values),max_speedup=max(values),
            below_baseline=sum(v<1 for v in values),algorithms=dict(Counter(r['algorithm_id'] for r in selected)))
    output.mkdir(parents=True,exist_ok=True)
    with (output/'p1-all-500.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    by_case={r['case_id']:{} for r in rows}
    for r in rows:by_case[r['case_id']][r['cores']]=r['baseline_speedup']
    with (output/'p1-speedup-100x5.csv').open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.writer(f);w.writerow(['case_id']+[f'k{k}' for k in range(1,6)])
        for case,values in sorted(by_case.items()):w.writerow([case]+[values[k] for k in range(1,6)])
    (output/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',required=True,type=Path);p.add_argument('--payload-dir',required=True,type=Path)
    p.add_argument('--output-dir',required=True,type=Path)
    a=p.parse_args();export(a.report,a.payload_dir,a.output_dir)
