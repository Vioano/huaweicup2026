#!/usr/bin/env python3
"""Audit fixed four-coordinate gap solver pilot; --archive is the only input mutation."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]; BASE=ROOT/'results/a/q2-nikolastarx/gap-solver-pilot-20260925'; RUN=BASE/'run'
COORDS=[('003',2),('005',3),('056',5),('008',5)]; FIELDS=('original_graph_copy_bytes','scheduled_copy_bytes','added_copy_bytes','partition_added_copy_bytes','spill_added_copy_bytes')
def sha(b):return hashlib.sha256(b).hexdigest()
def read(p):
 if not p.exists():p=p.with_name(p.name+'.gz')
 b=p.read_bytes()
 if b[:2]==b'\x1f\x8b': assert int.from_bytes(b[4:8],'little')==0;return gzip.decompress(b)
 return b
def parse(b):return json.loads(gzip.decompress(b) if b[:2]==b'\x1f\x8b' else b)
def pinned(o):return subprocess.check_output(['git','-C',str(ROOT),'show',f"{o['commit']}:{o['path']}"])
def canonical(p):return sha(json.dumps(p,sort_keys=True,allow_nan=False).encode())
def audit(archive=False,write=False):
 mb=(BASE/'manifest.json').read_bytes();m=json.loads(mb);s=json.loads((RUN/'summary.json').read_bytes());assert sha(mb)==s['manifest_sha256'] and s['status']=='completed' and s['solver_commit']==m['solver_commit']=='923b25ecb0b9d6d0e2d3f149fccef431b5403f99' and [(x['case'],x['cores']) for x in m['rows']]==[(x['case'],x['cores']) for x in s['rows']]==COORDS
 em=m['e2_manifest'];emraw=(ROOT/em['path']).read_bytes();emdoc=json.loads(emraw);assert sha(emraw)==em['sha256']==s['rows'][0]['solver_ledger']['source']['manifest_sha256'] and emdoc['e2_commit']==m['e2_commit']
 rows=[];files=[];calls={'solver':0,'E2_api':0,'native':0,'fallback':0,'E0_independent':0};processes=0;runnerhash=None
 for mr,sr,(case,k) in zip(m['rows'],s['rows'],COORDS):
  d=RUN/f'{case}-k{k}';sl=json.loads((d/'online/solver.json').read_text());led=sr['solver_ledger'];assert sr['status']=='accepted' and sr['case']==case and sr['cores']==k and led==sl and sl['source_checked'] and not sl['request_in_flight'] and not sr['solver_process_in_flight'] and not sr['independent_e0_in_flight']
  assert sl['solver_checkout_commit']==s['runner_commit'];assert sl['source']['commit']==m['e2_commit'] and sl['source']['manifest_sha256']==em['sha256'] and sl['source']['native_binary_sha256']==emdoc['binary']['sha256']; rh=sha(subprocess.check_output(['git','-C',str(ROOT),'show',f"{s['runner_commit']}:src/q2_nikolastarx/gap_solver_pilot.py"]));runnerhash=rh;assert sl['solver_source_sha256'].get('gap_solver_pilot.py')==rh
  for name,h in sl['solver_source_sha256'].items():
   if name!='gap_solver_pilot.py':assert m['solver_sources']['src/q2_nikolastarx/'+name]==h
  for pf in ('solver-process/process.json','e0-process/process.json'):
   p=json.loads((d/pf).read_text());processes+=1;assert p['exit_code']==0 and p['surviving_pids']==[]
  calls['solver']+=1;calls['E2_api']+=sl['calls']['E2_api_attempted'];calls['native']+=sl['calls']['native_returns'];calls['fallback']+=sl['calls']['E0_fallback'];calls['E0_independent']+=1
  attempts=sl['attempts'];assert len(attempts)==2 and all(a['status']=='native' and a['record']['route']=='native' and a['record']['official_code_hash']==attempts[0]['record']['official_code_hash'] for a in attempts)
  pbase=parse(pinned(mr['baseline_plan']));assert sha(pinned(mr['baseline_plan']))==mr['baseline_plan']['sha256'] and canonical(pbase)==attempts[0]['plan_sha256']
  truthraw=pinned(mr['baseline_truth']);truth=parse(truthraw);assert sha(truthraw)==mr['baseline_truth']['sha256'] and truth['makespan']==mr['baseline_m']
  a0=attempts[0]['record'];assert a0['makespan']==truth['makespan'] and a0['data_movement_bytes']==truth['data_movement_bytes'] and a0['cross_task_traffic']==truth['cross_task_traffic']
  a1=attempts[1]['record'];bs=(a0['makespan'],a0['data_movement_bytes']['added_copy_bytes']);cs=(a1['makespan'],a1['data_movement_bytes']['added_copy_bytes']);expected='baseline' if bs<=cs else 'candidate';selected=sl['detail']['selected'];assert selected==expected
  planraw=read(d/'plan.json');plan=parse(planraw);assert sha(planraw)==sl['plan_sha256'];chosen=attempts[0] if selected=='baseline' else attempts[1];assert canonical(plan)==chosen['plan_sha256'] and sr['selected_comparison']['plan_canonical_sha256']==canonical(plan)
  eraw=read(d/'result.json');e0=parse(eraw);rec=chosen['record'];assert sha(eraw)==sr['result']['result_sha256'] and e0['makespan']==rec['makespan']==sr['result']['makespan'] and e0['cross_task_traffic']==rec['cross_task_traffic']
  assert all(e0['data_movement_bytes'][f]==rec['data_movement_bytes'][f]==sr['result']['movement'][f] for f in FIELDS)
  rows.append({'case':case,'cores':k,'selected':selected,'baseline_makespan':a0['makespan'],'candidate_attempt_makespan':a1['makespan'],'selected_makespan':e0['makespan'],'delta_selected_makespan':e0['makespan']-a0['makespan'],'baseline_extra_ddr':a0['data_movement_bytes']['added_copy_bytes'],'candidate_attempt_extra_ddr':a1['data_movement_bytes']['added_copy_bytes'],'delta_candidate_extra_ddr':a1['data_movement_bytes']['added_copy_bytes']-a0['data_movement_bytes']['added_copy_bytes'],'solver_wall_seconds':sr['solver_process']['wall_seconds'],'solver_internal_wall_seconds':sl['internal_wall_seconds'],'external_e0_wall_seconds':sr['e0_process']['wall_seconds'],'selected_plan_raw_sha256':sha(planraw),'selected_plan_canonical_sha256':canonical(plan)})
  targets=[d/'result.json',d/'trace.json',d/'plan.json']+[p for p in (d/'online').rglob('*.json') if 'plan' in p.name.lower() and p.stat().st_size>20000]
  for src in targets:
   dst=src.with_name(src.name+'.gz')
   if archive and src.exists():
    raw=src.read_bytes()
    with dst.open('wb') as f:
     with gzip.GzipFile(filename='',fileobj=f,mode='wb',mtime=0) as z:z.write(raw)
    packed=dst.read_bytes();assert gzip.decompress(packed)==raw and sha(gzip.decompress(packed))==sha(raw) and int.from_bytes(packed[4:8],'little')==0;src.unlink()
   stored=dst if dst.exists() else src;packed=stored.read_bytes();raw=read(stored);assert raw
   files.append({'original_path':str(src.relative_to(ROOT)),'archive_path':str(dst.relative_to(ROOT)) if dst.exists() else None,'original_sha256':sha(raw),'stored_sha256':sha(packed),'original_bytes':len(raw),'stored_bytes':len(packed),'roundtrip_verified':bool(dst.exists()),'mtime':0 if dst.exists() else None})
 assert calls=={'solver':4,'E2_api':8,'native':8,'fallback':0,'E0_independent':4} and processes==8
 am=BASE/'archive-manifest.json'
 if am.exists():
  prior=json.loads(am.read_text());stored={x['archive_path']:x for x in files if x['archive_path']}
  assert len(prior['files'])==len(stored) and all(x['archive_path'] in stored and x['stored_sha256']==stored[x['archive_path']]['stored_sha256'] and x['original_sha256']==stored[x['archive_path']]['original_sha256'] for x in prior['files'])
 report={'status':'passed','coordinates':rows,'calls':calls,'processes':{'count':8,'all_exit_0':True,'all_surviving_pids_empty':True,'all_inflight_false':True},'source_identity':{'preflight_source_checked_all':True,'solver_sources_match_manifest_except_runner':True,'runner_script_sha256':runnerhash,'e2_manifest_sha256':em['sha256']},'online_plan_json_count':sum('/online/' in x['original_path'] for x in files),'limits':'Four targeted coordinates only. Solver process wall includes launch and online E2; internal wall is separately retained; independent E0 wall is separate. No full algorithm mean or time-budget causal claim.'}
 if write or archive:
  (BASE/'audit.json').write_text(json.dumps(report,indent=2)+'\n');(BASE/'archive-manifest.json').write_text(json.dumps({'schema':'gap-solver-pilot-archive-v1','files':files},indent=2)+'\n')
  (BASE/'SUMMARY.md').write_text('# Gap solver pilot audit\n\nFour targeted coordinates only. Baseline attempt 0 native record matches pinned baseline truth on M, five movement fields, and cross-task traffic. The selected full raw plan SHA matches the solver ledger; its canonical SHA binds to the selected attempt. Selection is the lexicographic minimum of complete baseline and candidate attempt scores. At 008, the candidate was worse and baseline was retained after two native E2 calls, not a zero-call test. The unselected candidate plan bytes were not retained, so its canonical hash is recorded but cannot be independently recomputed from plan bytes.\n\n| Case/k | Selection | Baseline M | Candidate attempt M | Selected M | Baseline → candidate extra DDR (B) | Solver process wall s | Internal solver wall s | External E0 wall s |\n|---|---|---:|---:|---:|---:|---:|---:|---:|\n'+''.join(f"| {r['case']}/k{r['cores']} | {r['selected']} | {r['baseline_makespan']} | {r['candidate_attempt_makespan']} | {r['selected_makespan']} | {r['baseline_extra_ddr']} → {r['candidate_attempt_extra_ddr']} | {r['solver_wall_seconds']:.3f} | {r['solver_internal_wall_seconds']:.3f} | {r['external_e0_wall_seconds']:.3f} |\n" for r in rows)+'\nAll 8 processes exited 0, left no surviving PIDs, and have no in-flight work. Totals: 4 solver processes, 8 native E2 records, 0 fallback, 4 independent E0. Solver and external E0 clocks are separate. This is not a full algorithm score or an isolated time-budget experiment; constructor wall is not claimed. Online directory contained no standalone plan JSON to archive. Archive hashes and mtime-zero roundtrips are in archive-manifest.json.\n')
 return report

def main():
 p=argparse.ArgumentParser();p.add_argument('--archive',action='store_true',help='compress selected JSON files, verify exact roundtrip, then remove originals and write reports');p.add_argument('--write-report',action='store_true',help='write audit.json, archive-manifest.json, SUMMARY.md without archiving inputs');a=p.parse_args();r=audit(a.archive,a.write_report);print(json.dumps({'status':r['status'],'calls':r['calls'],'coordinates':[(x['case'],x['selected'],x['solver_wall_seconds']) for x in r['coordinates']]}))
if __name__=='__main__':main()
