#!/usr/bin/env python3
"""Rebuild the one-record P3 export from retained originals; never evaluates."""
import gzip, hashlib, json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
BASE=ROOT/'results/a/q3-nikolastarx/convex-safe-one-shot-20260925'
RUN=BASE/'run'; RC=BASE/'resource-control'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):
 b=p.read_bytes(); return json.loads(gzip.decompress(b) if p.suffix=='.gz' else b)
def ref(p): return {'path':p.relative_to(ROOT).as_posix(),'sha256':sha(p)}
def main():
 run=load(RUN/'run.json'); w=load(RUN/'p3.worker.json'); rc=load(RC/'receipt.json'); result=load(RUN/'p3.json.gz')
 plan=BASE/'candidate/case_005_multicore_res.json'; baseline=ROOT/'results/benchmark-board/official-singlecore-20260924/005/result.json.gz'
 assert run['status']==rc['status']==w['status']=='complete' and run['source_commit']=='035b1452bd3c77261b2afc1ee2a9c341321d956c'
 assert w['counts_started']['P3']==1 and w['counts_started']['P2']==0 and run['candidate_M3']==result['makespan']==26427
 assert sha(plan)==run['plan_sha256']=='549519032c0ae7b78957463d0b6189d30184bcfd46e06fa60fc2c1fcc7dc6615'
 files=[BASE/'proposal-manifest.json',BASE/'frozen-admission/P3_CONVEX_005_K5_ADMISSION_20260925.json',BASE/'frozen-admission/P3_CONVEX_005_K5_ADMITTED_MANIFEST_20260925.json',BASE/'control.json',plan,RUN/'p3.json.gz',RUN/'run.json',RUN/'p3.worker.json',RUN/'p3.claim.json',RUN/'p3.reservation.json',RUN/'prepared.json.gz',RUN/'p3.stdout.txt',RUN/'p3.stderr.txt',RC/'receipt.json',RC/'samples.jsonl',RC/'stdout.txt',RC/'stderr.txt',baseline,ROOT/'data/raw/a/official/data/case_005.json',ROOT/'data/raw/a/official/data/config.txt']
 m={'schema':'convex-safe-005-p3-export-evidence-v1','source_commit':run['source_commit'],'plan_sha256':sha(plan),'admission_sha256':run['admission_sha256'],'official_code_sha256':run['official_code_sha256'],'references':{p.relative_to(ROOT).as_posix():ref(p) for p in files}}
 mp=OUT/'evidence-manifest.json'; mp.write_text(json.dumps(m,indent=2,ensure_ascii=False)+'\n')
 r=json.loads((OUT/'record-template.json').read_text())
 r['metrics'].update(makespan_cycles=result['makespan'],solver_wall_seconds=None,evaluation_wall_seconds=None,ddr_bytes=result['data_movement_bytes']['scheduled_copy_bytes'],extra_ddr_bytes=result['data_movement_bytes']['added_copy_bytes'],spill_bytes=result['data_movement_bytes']['spill_added_copy_bytes'],cache_hit_rate=result['cache_stats']['hit_rate'])
 r['observed_at']=w['finished_at']; r['identity']['plan_sha256']=sha(plan)
 r['artifacts']={'plan':ref(plan),'result':ref(RUN/'p3.json.gz'),'run':ref(RUN/'run.json'),'trace':ref(RUN/'p3.worker.json'),'log':ref(RUN/'p3.stdout.txt'),'manifest':ref(mp)}
 r['baseline']['result']=ref(baseline)
 feed={'schema_version':1,'submission_version':1,'records':[r]}
 (OUT/'board-feed-convex-safe-005-p3.json').write_text(json.dumps(feed,indent=2,ensure_ascii=False)+'\n')
 print('feed_sha256',sha(OUT/'board-feed-convex-safe-005-p3.json'))
 print('evidence_manifest_sha256',sha(mp))
if __name__=='__main__': main()
