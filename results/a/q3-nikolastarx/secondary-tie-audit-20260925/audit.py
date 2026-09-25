"""Read all frozen 500 receipts and hash-check equal-M rejected raw candidates."""
import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess

SOURCE = 'bff88a66cd76ceb2d75242bf99d34bfe8b1879d4'
PREFIX = 'results/a/q3-nikolastarx/forest-full500-20260925-s59'
OUT = Path(__file__).resolve().parent


def sha(raw):return hashlib.sha256(raw).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-root', type=Path, required=True)
    a = p.parse_args()
    paths = subprocess.check_output(['git','ls-tree','-r','--name-only',SOURCE,PREFIX],text=True).splitlines()
    paths = [p for p in paths if p.endswith('/evidence/receipt.json')]
    assert len(paths)==500
    process = subprocess.run(['git','cat-file','--batch'],
        input=''.join(SOURCE+':'+p+'\n' for p in paths).encode(),stdout=subprocess.PIPE,check=True)
    stream = io.BytesIO(process.stdout)
    rawdir=OUT/'raw';rawdir.mkdir(exist_ok=True)
    rows=[];bound_ties=[]
    for path in paths:
        header=stream.readline().decode().split();raw=stream.read(int(header[2]))
        assert stream.read(1)==b'\n'
        d=json.loads(raw)
        for c in d['candidates']:
            if c.get('status')=='bound_pruned' and c.get('certified_lower_bound_cycles')==d['makespan']:
                bound_ties.append({'receipt':path,'candidate':c['name']})
            if (c.get('status')!='ok' or c.get('makespan')!=d['makespan'] or
                c.get('artifacts',{}).get('plan',{}).get('sha256')==d['plan_sha256']):continue
            name=Path(path).parts[-3]+'-'+c['name'];saved={}
            for kind,ref in c['artifacts'].items():
                payload=(a.native_root/Path(path).parent/ref['path']).read_bytes()
                assert sha(payload)==ref['sha256']
                dest=rawdir/(name+'-'+Path(ref['path']).name)
                dest.write_bytes(payload)
                saved[kind]={'path':dest.relative_to(OUT).as_posix(),'sha256':sha(payload)}
            result=json.loads(gzip.decompress((OUT/saved['result']['path']).read_bytes()))
            assert result['makespan']==d['makespan']
            receipt_path=rawdir/(name+'-receipt.json');receipt_path.write_bytes(raw)
            row={'receipt_git_path':path,'receipt_sha256':sha(raw),'candidate':c['name'],
                 'case_coordinate':Path(path).parts[-3],'M':d['makespan'],
                 'selected_plan_sha256':d['plan_sha256'],'candidate_artifacts':saved,
                 'extra_delta':result['data_movement_bytes']['added_copy_bytes']-d['data_movement_bytes']['added_copy_bytes'],
                 'spill_delta':result['data_movement_bytes']['spill_added_copy_bytes']-d['data_movement_bytes']['spill_added_copy_bytes'],
                 'hit_rate_delta':result['cache_stats']['hit_rate']-d['cache_stats']['hit_rate']}
            rows.append(row)
    counts={key:{'lower':sum(r[key]<0 for r in rows),'equal':sum(r[key]==0 for r in rows),
                 'higher':sum(r[key]>0 for r in rows)} for key in ['extra_delta','spill_delta','hit_rate_delta']}
    report={'source_commit':SOURCE,'receipts_checked':500,'unselected_equal_M_distinct_plans':len(rows),
            'counts':counts,'equal_bound_pruned':bound_ties,'rows':rows,'new_official_calls':0,
            'scope':'Retrospective mechanism audit; not a new solver or a composed full500 score. Candidate raw result/plan bytes checked against frozen receipts; no independent re-evaluation. No P2 for alternative plans.'}
    (OUT/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'candidates':len(rows),'counts':counts,'equal_bound_pruned':len(bound_ties),
                      'raw_bytes':sum(p.stat().st_size for p in rawdir.iterdir()),'E0':0}))


if __name__=='__main__':main()
