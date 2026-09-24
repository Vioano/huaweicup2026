"""Construct six chain-packet plans and inspect their static costs; no scoring."""
from pathlib import Path
import gzip
import hashlib
import json
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from src.q2_nikolastarx.chain_packets import build
from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
from src.q2_nikolastarx.adaptive_semantic import read_evaluation_config, read_scene_b_config

SOURCE='47baf7f89948aa0a1ea2038c823e60513c78f160'


def main():
    for name in sorted((ROOT/'src/q2_nikolastarx').glob('*.py')):
        assert name.read_bytes()==subprocess.check_output(['git','show',f'{SOURCE}:{name.relative_to(ROOT)}'],cwd=ROOT),name
    config_path=ROOT/'data/raw/a/official/data/config.txt'
    config={**read_evaluation_config(config_path),**read_scene_b_config(config_path)}
    parent=Path(__file__).parent
    prior=json.loads((parent/'summary.json').read_text())
    out=parent/'chain-preflight'
    out.mkdir(exist_ok=False)
    rows=[]
    for r in prior['rows']:
        case=r['case']; raw=(ROOT/f'data/raw/a/official/data/case_{case}.json').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==r['graph_sha256']
        graph=json.loads(raw)
        plan,detail=build(graph,5,config)
        count=mandatory_copy_work(graph,plan,config['bandwidth'])
        predicted=detail['predicted_ddr_bytes_without_spill']
        assert sum(predicted.values())==count['transfer_bytes']
        plan_bytes=(json.dumps(plan,ensure_ascii=False,separators=(',',':'))+'\n').encode()
        filename=f'{case}-k5-plan.json.gz'; packed=gzip.compress(plan_bytes,mtime=0)
        (out/filename).write_bytes(packed)
        rows.append({'case':case,'graph_sha256':r['graph_sha256'],
                     'plan':{'path':filename,'sha256':hashlib.sha256(packed).hexdigest(),
                             'uncompressed_sha256':hashlib.sha256(plan_bytes).hexdigest()},
                     'detail':detail,'mandatory_copy':count,
                     'baseline_existing_E0_M':r['existing_E0_M'],
                     'work_exceeds_baseline_M':count['service_work']>r['existing_E0_M'],
                     'new_E0_status':'not_run'})
    report={'source_commit':SOURCE,'python':platform.python_version(),
            'config_sha256':hashlib.sha256(config_path.read_bytes()).hexdigest(),
            'calls':{'construction':len(rows),'E0':0,'E1':0,'E2':0},
            'scope':'Constructed candidates and static cost checks only; no new makespan or end-to-end solver speed result.',
            'rows':rows}
    (out/'summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps([{'case':r['case'],'packets':r['detail']['packet_count'],
                       'DDR_work':r['mandatory_copy']['service_work'],
                       'baseline_M':r['baseline_existing_E0_M'],
                       'reject':r['work_exceeds_baseline_M']} for r in rows],indent=2))


if __name__=='__main__':main()
