import csv, json, urllib.request, math, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[3]
BPATH=ROOT/'results/a/q3-nikolastarx/global-bounds-20260925/bounds.csv'
REPORT=ROOT/'results/a/q3-nikolastarx/global-bounds-20260925/REPORT.md'
URL='http://127.0.0.1:52341/api/v1/cells?problem=P3&run=q3-forest-full500-20260925-s59'
ALGORITHM='q3-forest-memory-witness'; SOLVER='311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1'
CONFIG='dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'; OFFICIAL='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
assert hashlib.sha256(BPATH.read_bytes()).hexdigest()=='bb8a21066f228f428ca2cab3d742c2eb6247cfbf1b281b30c588029a6ba9cd86'
rows=list(csv.DictReader(BPATH.open()))
assert len(rows)==500
bounds={(r['case_id'],int(r['cores'])):r for r in rows}
assert len(bounds)==500 and set(bounds)=={(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)}
snapshot_path=HERE/'cells-snapshot.json'
if snapshot_path.exists():
    api=json.loads(snapshot_path.read_text())
else:
    with urllib.request.urlopen(URL,timeout=20) as resp: full=json.load(resp)
    api={'as_of':full['as_of'],'cursor':full['cursor'],'cells':[]}
    keep=['id','problem','case_id','cores','eligible','status','run_id','algorithm_id','solver_commit','baseline_verified','evaluator','identity','baseline','metrics','artifacts']
    for cell in full['cells']:
        r=cell.get('best')
        api['cells'].append({'problem':cell['problem'],'case_id':cell['case_id'],'cores':cell['cores'],'best':{k:r[k] for k in keep} if r else None})
    snapshot_path.write_text(json.dumps(api,ensure_ascii=False,indent=2)+'\n')
assert len(api['cells'])==500
cells={}
for cell in api['cells']:
    key=(cell['case_id'],cell['cores']); assert key not in cells and key in bounds
    r=cell.get('best'); assert r and r.get('eligible') is True and r.get('status')=='ok'
    assert r.get('problem')=='P3' and r.get('run_id')=='q3-forest-full500-20260925-s59'
    assert r.get('algorithm_id')==ALGORITHM and r.get('solver_commit')==SOLVER
    assert r.get('baseline_verified') is True and r.get('evaluator',{}).get('route')=='E0'
    ident=r['identity']; br=r['baseline']; b=bounds[key]
    assert ident['graph_sha256']==b['graph_sha256'] and ident['config_sha256']==CONFIG and ident['official_sha256']==OFFICIAL
    assert br['graph_sha256']==ident['graph_sha256'] and br['config_sha256']==CONFIG and br['official_sha256']==OFFICIAL
    assert cell['problem']=='P3' and r['case_id']==key[0] and r['cores']==key[1]
    B=int(b['official_baseline_cycles']); L=int(b['lower_bound_cycles']); T=r['metrics']['makespan_cycles']
    assert 0<L<=T and math.isclose(r['metrics']['baseline_speedup'],B/T,rel_tol=1e-12)
    slack=(B/L-B/T)/100
    cells[key]={'case_id':key[0],'cores':key[1],'B':B,'L':L,'T':T,'upper_speedup':B/L,'current_speedup':B/T,'remaining_mean_increment':slack,'record_id':r['id'],'plan_sha256':ident['plan_sha256'],'result_sha256':r['artifacts']['result']['sha256'],'graph_sha256':ident['graph_sha256']}
assert len(cells)==500
bycore={}
for k in range(1,6):
    cs=[cells[(f'{i:03d}',k)] for i in range(1,101)]
    bycore[str(k)]={'n':100,'current_mean_speedup':sum(x['current_speedup'] for x in cs)/100,'bound_mean_speedup':sum(x['upper_speedup'] for x in cs)/100,'remaining_mean_slack':sum(x['remaining_mean_increment'] for x in cs),'residual_difference':sum(x['upper_speedup']-x['current_speedup'] for x in cs)/100}
core5=sorted([cells[(f'{i:03d}',5)] for i in range(1,101)],key=lambda x:(-x['remaining_mean_increment'],x['case_id']))
rank097=next(i for i,x in enumerate(core5,1) if x['case_id']=='097')
profile= json.loads((ROOT/'results/a/q3-nikolastarx/input-residency-profile-20260925/profile.json').read_text())
family={r['case_id'] for r in profile['records']}
assert all(cells[(r['case_id'],5)]['graph_sha256']==r['graph_sha256'] for r in profile['records'])
out={'schema':'q3-current-forest-bound-v1','api_as_of':api['as_of'],'api_cursor':api['cursor'],'api_run':'q3-forest-full500-20260925-s59','accepted_records':500,'algorithm_id':ALGORITHM,'solver_commit':SOLVER,'coverage_per_core':{str(k):sum((f'{i:03d}',k) in cells for i in range(1,101)) for k in range(1,6)},'identity_checks':{'bounds_rows':len(rows),'graph_hash_matches_all_500':True,'config_hash_matches_all_500':True,'official_hash_matches_all_500':True,'baseline_verified_all_500':True,'exact_source_run_algorithm_all_500':True},'formula':'delta_i=(B_i/L_i - B_i/T_i)/100; B=official single-core M, L=frozen compute-only lower bound, T=current selected forest500 P3 M. Upper slack only, not attainable guarantee.','by_cores':bycore,'core5_top10':core5[:10],'case097':{'rank_among_100':rank097,'remaining_mean_increment':cells[('097',5)]['remaining_mean_increment'],'current_speedup':cells[('097',5)]['current_speedup'],'bound_speedup':cells[('097',5)]['upper_speedup']},'top10_contribution_sum':sum(x['remaining_mean_increment'] for x in core5[:10]),'cartesian_family_potential':{'case_ids':sorted(family),'five_core_remaining_mean_increment':sum(cells[(case,5)]['remaining_mean_increment'] for case in family),'source':'input-residency-profile-20260925/profile.json; graph hashes matched'},'bound_csv_sha256':hashlib.sha256(BPATH.read_bytes()).hexdigest(),'selected_cells_snapshot_sha256':hashlib.sha256(snapshot_path.read_bytes()).hexdigest(),'scope_note':'Uses only the current same-run P3 best for this single fixed algorithm, not the historical per-cell winner. Saves only selected cells, not unrelated runtime/admission records; does not rehash 500 result blobs or rerun E0. Bounds are the earlier frozen compute/CP relaxation; not plan-aware and not a promise.'}
(HERE/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'as_of':api['as_of'],'cursor':api['cursor'],'by_cores':bycore,'top10_cases':[r['case_id'] for r in core5[:10]],'097':out['case097'],'top10_sum':out['top10_contribution_sum']},indent=2))
