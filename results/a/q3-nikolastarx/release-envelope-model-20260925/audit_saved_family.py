"""Conditional signatures of saved-graph cold-input breakpoints; zero official calls."""
from pathlib import Path
import gzip
import hashlib
import importlib.util
import json
import time

from model import uniformly_no_slower
from task_profile import task_signature

HERE=Path(__file__).resolve().parent
BASE=HERE.parent


def main():
    start=time.perf_counter()
    compiler=BASE/'partial-bucket-compile-20260925/compile.py'
    spec=importlib.util.spec_from_file_location('saved_partial_compiler',compiler)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    p=BASE/'pipeline-prefix-static-20260925'
    paths=[p/'case_044_multicore_res.json',p/'snapshots.json.gz',p/'certificate.json']
    expected=['13914b24c18b59366be17de86a26d227ff85427cb00b184799587777547a6508',
              '91b8aad332a276345be824ffeda799564439ca61c48a5418053eec8068e1f471',
              'fa6689b6f8770def845138b64856b63c1f62ef3f0317c325ada2fa8a5ea56595']
    for f,sha in zip(paths,expected):
        assert hashlib.sha256(f.read_bytes()).hexdigest()==sha
    plan=json.loads(paths[0].read_text())
    snapshots=json.loads(gzip.decompress(paths[1].read_bytes()))
    certificate=json.loads(paths[2].read_text())
    c=2;task=snapshots['candidate'][str(c)]
    original={int(u):sg for u,sg in plan['node_to_subgraph'].items()}
    pilot=[u for u in task['pre_step2_word'] if original.get(u)==plan['core_schedules'][c][0]]
    family=json.loads((BASE/'partial-bucket-compile-20260925/structure-table.json').read_text())
    assert family['family']=='cold-input breakpoint restricted family'
    rows=[]
    # Include original full prefix as a structural control; do not call E0.
    for h in [r['h'] for r in family['breakpoints']]+[len(pilot)]:
        if h==len(pilot):
            word=task['pre_step2_word'];facts={'head_prefix_cold_count':7}
        else:
            _,words,facts=mod.compile_split(plan,snapshots,certificate,c,h)
            word=words[str(c)]
        row=task_signature(task['graph'],word,pilot,snapshots['cross_links'],c,60)
        row.update(h=h,q=facts['head_prefix_cold_count'])
        rows.append(row)
    for a in rows:
        a['strictly_model_dominated_by']=[b['h'] for b in rows
            if b is not a and uniformly_no_slower(b['signature'],a['signature'])
            and b['signature']!=a['signature']]
        a['same_model_signature_as']=[b['h'] for b in rows if b is not a and b['signature']==a['signature']]
    files=[*paths,compiler,HERE/'model.py',HERE/'task_profile.py',Path(__file__),
           BASE/'partial-bucket-compile-20260925/structure-table.json']
    result={'scope':'044 core2 first pilot, fixed rounded exclusive DDR services and arbitrary independent upstream releases; model coefficients only, not official dominance or scores',
            'source_sha256':{str(f.relative_to(BASE.parents[3])):hashlib.sha256(f.read_bytes()).hexdigest() for f in files},
            'core':c,'source_family':'cold-input breakpoint restricted family plus original full prefix',
            'rows':rows,'wall_seconds':time.perf_counter()-start,
            'calls':{'Task':0,'Step1':0,'Step2':0,'Step3':0,'E0':0,'solver':0,'VM':0}}
    (HERE/'saved-family.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps([{k:r[k] for k in ('h','q','signature','strictly_model_dominated_by','same_model_signature_as')} for r in rows],indent=2))


if __name__=='__main__':
    main()
