#!/usr/bin/env python3
"""One-shot orchestration: <=1 child process per case, stop on first failure."""
import argparse, datetime, hashlib, json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def canon(obj): return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf-8')
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--manifest',required=True); a=ap.parse_args()
    mp=(ROOT/a.manifest).resolve(); m=json.loads(mp.read_text()); out=mp.parent
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=m['frozen_commit']: raise SystemExit('HEAD mismatch')
    if sha(ROOT/m['source_path'])!=m['source_sha256']: raise SystemExit('frozen source SHA mismatch')
    if sha(ROOT/m['helper_path'])!=m['helper_sha256'] or sha(ROOT/m['runner_path'])!=m['runner_sha256']: raise SystemExit('frozen harness SHA mismatch')
    if any(sha(ROOT/path)!=value for path,value in m['official_parser_sha256'].items()): raise SystemExit('frozen config parser SHA mismatch')
    if (out/'run_claim.json').exists() or (out/'run_summary.json').exists() or any((out/f"case_{c['case_id']}").exists() for c in m['cases']): raise SystemExit('prior claim/output exists; refuse rerun')
    for c in m['cases']:
        if sha(ROOT/c['graph'])!=c['graph_sha256'] or sha(ROOT/c['candidate_plan'])!=c['candidate_plan_sha256'] or sha(ROOT/c['candidate_metadata'])!=c['candidate_metadata_sha256']: raise SystemExit(f"{c['case_id']} frozen input/candidate SHA mismatch")
    cfg=ROOT/m['config_path']
    if sha(cfg)!=m['config_sha256']: raise SystemExit('config SHA mismatch')
    sys.path.insert(0,str(ROOT/'data/raw/a/official/code'))
    from evaluation_validation import read_evaluation_config
    from multicore_cut_evaluate_problem_2 import read_scene_b_config
    cap=read_evaluation_config(str(cfg))['capacity']; delay=read_scene_b_config(str(cfg))['cross_core_copy_delay_cycles']
    if cap!=m['capacity'] or delay!=m['cross_delay_cycles']: raise SystemExit('official config parser value mismatch')
    if m['status']!='frozen-before-execution': raise SystemExit('manifest state mismatch')
    summary={'id':m['id'],'frozen_commit':m['frozen_commit'],'source_sha256':m['source_sha256'],'config_capacity':cap,'cross_delay_cycles':delay,'overall_started_at':utc(),'results':[],'official_calls':{'Task':0,'Step':0,'E0':0,'E1':0,'E2':0,'pipe_bound':0}}
    (out/'run_claim.json').write_text(json.dumps({'claimed_at':summary['overall_started_at'],'pid':os.getpid(),'manifest_sha256':sha(mp)},indent=2)+'\n')
    for c in m['cases']:
        case=c['case_id']; d=out/f'case_{case}'; d.mkdir(exist_ok=False)
        if sha(ROOT/c['graph'])!=c['graph_sha256'] or sha(ROOT/c['candidate_plan'])!=c['candidate_plan_sha256'] or sha(ROOT/c['candidate_metadata'])!=c['candidate_metadata_sha256']: raise SystemExit(f'{case} frozen input/candidate SHA mismatch')
        for key,dest in [('candidate_plan','candidate_plan.json'),('candidate_metadata','candidate_metadata.json')]:
            src=ROOT/c[key]
            if key=='candidate_plan' and sha(src)!=c['candidate_plan_sha256']: raise SystemExit(f'{case} candidate SHA mismatch')
            (d/dest).write_bytes(src.read_bytes())
        start=utc(); t0=time.monotonic(); (d/'claim.json').write_text(json.dumps({'case_id':case,'claimed_at':start,'pid':os.getpid(),'attempt':1},indent=2)+'\n')
        cmd=c['command']
        if cmd[0]!=sys.executable: raise SystemExit('frozen child interpreter mismatch')
        try:
            p=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True,timeout=m['budget']['per_case_seconds'],check=False)
            elapsed=time.monotonic()-t0; end=utc(); (d/'stdout.txt').write_text(p.stdout,encoding='utf-8'); (d/'stderr.txt').write_text(p.stderr,encoding='utf-8')
            r={'case_id':case,'status':'constructed' if p.returncode==0 else 'failed','started_at':start,'finished_at':end,'wall_seconds':elapsed,'command':cmd,'exit_code':p.returncode,'stdout_path':(d/'stdout.txt').relative_to(ROOT).as_posix(),'stderr_path':(d/'stderr.txt').relative_to(ROOT).as_posix()}
            if p.returncode!=0: r['error']='constructor child returned nonzero; stop; no retry'
            else:
                gp=d/'constructed/plan.json'; cp=d/'candidate_plan.json'; generated=json.loads(gp.read_text()); expected=json.loads(cp.read_text())
                gc=hashlib.sha256(canon(generated)).hexdigest(); cc=hashlib.sha256(canon(expected)).hexdigest()
                cmp={'case_id':case,'object_equal':generated==expected,'canonical_json_equal':canon(generated)==canon(expected),'generated_raw_sha256':sha(gp),'candidate_raw_sha256':sha(cp),'generated_canonical_sha256':gc,'candidate_canonical_sha256':cc,'raw_bytes_equal':gp.read_bytes()==cp.read_bytes(),'expected_candidate_sha256':c['candidate_plan_sha256']}
                (d/'comparison.json').write_text(json.dumps(cmp,indent=2)+'\n'); r['comparison_path']=(d/'comparison.json').relative_to(ROOT).as_posix(); r['comparison']=cmp
                if not cmp['object_equal'] or not cmp['canonical_json_equal']: r['status']='comparison_failed'; r['error']='plan mismatch; stop; no retry'
            summary['results'].append(r); (out/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
            if r['status']!='constructed' or (r.get('comparison') and not r['comparison']['canonical_json_equal']): break
        except subprocess.TimeoutExpired as e:
            elapsed=time.monotonic()-t0; end=utc(); (d/'stdout.txt').write_bytes(e.stdout or b''); (d/'stderr.txt').write_bytes(e.stderr or b'')
            r={'case_id':case,'status':'timeout','started_at':start,'finished_at':end,'wall_seconds':elapsed,'command':cmd,'error':'60-second constructor timeout; stop; no retry'}
            summary['results'].append(r); (out/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); break
    summary['overall_finished_at']=utc(); (out/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'results':[{k:r.get(k) for k in ('case_id','status','wall_seconds','error')} for r in summary['results']],'official_calls':summary['official_calls']},ensure_ascii=False))
    return 0 if len(summary['results'])==len(m['cases']) and all(r['status']=='constructed' for r in summary['results']) else 1
if __name__=='__main__': raise SystemExit(main())
