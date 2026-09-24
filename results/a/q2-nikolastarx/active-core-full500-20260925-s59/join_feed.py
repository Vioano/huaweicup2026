"""Join the four complete fixed P2 shards into one standard submission feed."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
AREA=Path(__file__).resolve().parent
SOURCE='2794ceba93acc1f7fc119154f61082511843d4b3'
RUNNER='7483614f356099a2a8c89967241b8e9ebdb77c08'
GROUP='q2-activecore-full500-20260925-s59'

def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
 p=argparse.ArgumentParser();p.add_argument('--batch',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 batch=a.batch.resolve();out=a.output.resolve()
 if batch.parent!=AREA or out.parent!=batch or out.exists():p.error('fresh producer batch/output required')
 dispatch=read(batch/'dispatch.json')
 if dispatch['status']!='complete' or dispatch['source_commit']!=SOURCE or dispatch['runner_commit']!=RUNNER:
  raise RuntimeError('fixed dispatch incomplete or changed')
 if len(dispatch['shards'])!=4 or any(not x['accepted'] or x['cell_count']!=125 for x in dispatch['shards'].values()):
  raise RuntimeError('four full accepted shards required')
 dispatch_sha=sha(batch/'dispatch.json')
 rows=[];coords=set();calls={'solver':0,'E0':0,'E1':0,'E2':0}
 for n in range(1,5):
  shard=batch/f's{n:02}';journal=read(shard/'journal.json')
  if journal['identity']['source_commit']!=SOURCE or journal['identity']['runner_commit']!=RUNNER or journal['stop_reason']!='all_fixed_cells_dispatched' or len(journal['cells'])!=125:
   raise RuntimeError(f'shard {n} journal mismatch')
  native=f'q2-activecore-full500-20260925-s59-s{n:02}'
  for key,item in sorted(journal['cells'].items()):
   if item['state']!='ok' or item['calls']!={'solver':1,'E0':1,'E1':0,'E2':0}:
    raise RuntimeError(f'invalid call ledger {key}')
   for call,value in item['calls'].items():calls[call]+=value
   path=shard/f'board-feed-{key}.json';payload=read(path)
   if payload['schema_version']!=1 or payload['submission_version']!=1 or len(payload['records'])!=1:
    raise RuntimeError(f'invalid cell feed {key}')
   row=payload['records'][0];coord=(row['case_id'],row['cores'])
   if row['status']!='ok' or row['solver_commit']!=SOURCE or row['run_id']!=native or coord in coords or key!=f'{coord[0]}-k{coord[1]}':
    raise RuntimeError(f'cell identity mismatch {key}')
   for ref in row['artifacts'].values():
    file=ROOT/ref['path']
    if not file.is_file() or sha(file)!=ref['sha256']:
     raise RuntimeError(f'artifact mismatch {key}: {ref["path"]}')
   baseline=row['baseline']['result'];file=ROOT/baseline['path']
   if not file.is_file() or sha(file)!=baseline['sha256']:
    raise RuntimeError(f'baseline mismatch {key}')
   coords.add(coord)
   row['run_id']=GROUP
   row['parameters'].update(native_shard_run_id=native,global_workers_max=4,
      dispatch_receipt_sha256=dispatch_sha)
   row['notes'].append('Four fixed disjoint 125-cell shards form one source version; previous 044/k4 pilot is not reused. Each solver launched a separate final official P2 E0. Shared-host concurrency is recorded separately from solver wall.')
   row['notes'].append('The matrix runner environment reports Python 3.14.5; the recorded solver and official E0 argv both use .venv/bin/python, prepared by uv sync --locked and verified as Python 3.12.13. The environment field describes the outer runner, not the solver interpreter.')
   rows.append(row)
 expected={(f'{i:03d}',k) for i in range(1,101) for k in range(1,6)}
 if coords!=expected or calls!={'solver':500,'E0':500,'E1':0,'E2':0}:
  raise RuntimeError('full coverage or call budget mismatch')
 out.write_text(json.dumps({'schema_version':1,'submission_version':1,'records':rows},ensure_ascii=False,indent=2,allow_nan=False)+'\n')
 print(json.dumps({'feed':out.relative_to(ROOT).as_posix(),'records':len(rows),'calls':calls,'sha256':sha(out)}))
if __name__=='__main__':main()
