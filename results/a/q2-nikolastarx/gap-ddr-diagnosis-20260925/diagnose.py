#!/usr/bin/env python3
"""Read fixed Git pilot artifacts and count original mandatory COPY work only."""
import sys
sys.dont_write_bytecode = True
import csv, gzip, hashlib, json, subprocess
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
OUT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
PILOT='a6b09dcebf26c5ac28bcb4378dec8dbf06b0c075'

def blob(rev,path): return subprocess.check_output(['git','-C',str(ROOT),'show',f'{rev}:{path}'])
def sha(b): return hashlib.sha256(b).hexdigest()
def jblob(rev,path): return json.loads(blob(rev,path))
def gzjson(b): return json.loads(gzip.decompress(b))
def original_input(row, field):
    ref=row[field]; b=blob(ref['commit'],ref['path'])
    if sha(b)!=ref['sha256']: raise ValueError(f'{field} SHA mismatch {row["case"]}')
    return gzjson(b) if ref['path'].endswith('.gz') else json.loads(b)

def count_pairs(graph, plan):
    from src.q2_nikolastarx.direct import derive_multicore_plan
    from multicore_cut_evaluate_problem_1 import _original_tensor_views
    view=derive_multicore_plan(graph,plan); mapping=view['mapping']; core_sg=view['core_by_subgraph']
    core_op={op:core_sg[sg] for op,sg in mapping.items()}
    producers,consumers,_=_original_tensor_views(graph)
    out={}
    for t in graph['tensors']:
        tid,size=t['id'],t['size']
        src={core_op[o] for o in producers.get(tid,()) if o in mapping}
        dst={core_op[o] for o in consumers.get(tid,()) if o in mapping}
        for a in src:
            for b in dst:
                if a!=b: out[(tid,a,b)]=2*size
    return out

def main():
    for source_path in ('src/q2_nikolastarx/candidate_ddr.py', 'src/q2_nikolastarx/direct.py', 'data/raw/a/official/code/multicore_cut_evaluate_problem_1.py'):
     if (ROOT/source_path).read_bytes()!=blob(PILOT,source_path): raise ValueError('Static counter source drift: '+source_path)
    from src.q2_nikolastarx.candidate_ddr import mandatory_copy_work
    mp=f'results/a/q2-nikolastarx/gap-solver-pilot-20260925/manifest.json'
    mbytes=blob(PILOT,mp); manifest=json.loads(mbytes)
    sm=json.loads(blob(PILOT,'results/a/q2-nikolastarx/gap-solver-pilot-20260925/run/summary.json'))
    am=json.loads(blob(PILOT,'results/a/q2-nikolastarx/gap-solver-pilot-20260925/archive-manifest.json'))
    archive={x['archive_path']:x for x in am['files']}
    rows=[]; top_tensors={}; pair_deltas={}
    for rec in manifest['rows']:
        case=rec['case']; cores=rec['cores']; key=f'{case}-k{cores}'; d=f'results/a/q2-nikolastarx/gap-solver-pilot-20260925/run/{case}-k{cores}/'
        graph_b=(ROOT/rec['graph']['path']).read_bytes()
        if sha(graph_b)!=rec['graph']['sha256']: raise ValueError(f'graph SHA mismatch {key}')
        graph=json.loads(graph_b)
        oldplan=original_input(rec,'baseline_plan'); oldtruth=original_input(rec,'baseline_truth')
        oldplan_sha=sha(blob(rec['baseline_plan']['commit'],rec['baseline_plan']['path']))
        oldtruth_sha=sha(blob(rec['baseline_truth']['commit'],rec['baseline_truth']['path']))
        ppath=d+'plan.json.gz'; rpath=d+'result.json.gz'
        for p in (ppath,rpath):
            if p not in archive: raise ValueError(f'archive entry missing {p}')
            stored=blob(PILOT,p)
            if sha(stored)!=archive[p]['stored_sha256']: raise ValueError(f'archive SHA mismatch {p}')
        newplan_b=gzip.decompress(blob(PILOT,ppath)); newplan=json.loads(newplan_b)
        newtruth=gzjson(blob(PILOT,rpath))
        if sha(newplan_b)!=archive[ppath]['original_sha256'] or sha(gzip.decompress(blob(PILOT,rpath)))!=archive[rpath]['original_sha256']:
            raise ValueError(f'roundtrip SHA mismatch {key}')
        assert newtruth['num_cores']==oldtruth['num_cores']==cores
        old=mandatory_copy_work(graph,oldplan,60); new=mandatory_copy_work(graph,newplan,60)
        oldx=oldtruth['data_movement_bytes']; newx=newtruth['data_movement_bytes']
        recrow={'case':case,'cores':cores,'selection':'baseline_retained' if sha(newplan_b)==oldplan_sha else 'candidate_selected','artifact_sha256':{'graph':sha(graph_b),'old_plan':oldplan_sha,'old_truth':oldtruth_sha,'selected_plan':sha(newplan_b),'selected_truth_gzip':sha(blob(PILOT,rpath))},'old':old,'new':new,
          'old_E0':{'makespan':oldtruth['makespan'],'scheduled_copy_bytes':oldx['scheduled_copy_bytes'],'spill_added_copy_bytes':oldx['spill_added_copy_bytes']},
          'new_E0':{'makespan':newtruth['makespan'],'scheduled_copy_bytes':newx['scheduled_copy_bytes'],'spill_added_copy_bytes':newx['spill_added_copy_bytes']},
          'zero_spill_copy_match':{'old':oldx['spill_added_copy_bytes']==0 and old['transfer_bytes']==oldx['scheduled_copy_bytes'],'new':newx['spill_added_copy_bytes']==0 and new['transfer_bytes']==newx['scheduled_copy_bytes']}}
        rows.append(recrow)
        a=count_pairs(graph,oldplan); b=count_pairs(graph,newplan); keys=set(a)|set(b)
        for tk in keys:
            delta=b.get(tk,0)-a.get(tk,0)
            if delta>0:
                tid,src,dst=tk; bucket=top_tensors.setdefault(key,defaultdict(lambda:{'delta_bytes':0,'new_bytes':0,'old_bytes':0,'pairs':[]}))
                z=bucket[tid]; z['delta_bytes']+=delta; z['new_bytes']+=b.get(tk,0); z['old_bytes']+=a.get(tk,0); z['pairs'].append({'src_core':src,'dst_core':dst,'old_bytes':a.get(tk,0),'new_bytes':b.get(tk,0),'delta_bytes':delta})
        pair_deltas[key]={'old_pair_count':len(a),'new_pair_count':len(b),'increased_pair_bytes':sum(max(0,b.get(t,0)-a.get(t,0)) for t in keys),'decreased_pair_bytes':sum(max(0,a.get(t,0)-b.get(t,0)) for t in keys)}
    result={'pilot_commit':PILOT,'manifest_sha256':sha(mbytes),'baseline_commit':manifest['baseline_commit'],'rule':'mandatory_copy_work transfer_bytes counted by category before Step2 spill; per-tensor cross transfer counts one OUT+IN per (tensor,src core,dst core).','cells':rows,'cross_tensor_pair_deltas':pair_deltas,'top_increased_tensors':{k:[{'tensor_id':tid,**v} for tid,v in sorted(tens.items(),key=lambda q:(-q[1]['delta_bytes'],str(q[0])))[:10]] for k,tens in top_tensors.items()},'tensor_concentration':{k:{'increased_tensor_count':len(tens),'positive_pair_delta_bytes':sum(v['delta_bytes'] for v in tens.values()),'top10_positive_delta_bytes':sum(v['delta_bytes'] for _,v in sorted(tens.items(),key=lambda q:(-q[1]['delta_bytes'],str(q[0])))[:10]),'max_cross_core_pairs_per_tensor':max((len(v['pairs']) for v in tens.values()),default=0)} for k,tens in top_tensors.items()}}
    (OUT/'diagnosis.json').write_text(json.dumps(result,indent=2)+'\n')
    write_summary(result)
    print(json.dumps({'cells':[{ 'case':r['case'],'selection':r['selection'],'old':r['old']['categories'],'new':r['new']['categories'],'zero_spill_match':r['zero_spill_copy_match']} for r in rows], 'top':{k:v[:5] for k,v in result['top_increased_tensors'].items()}},ensure_ascii=False))

def write_summary(d):
    lines=['# Static mandatory COPY diagnosis','',f"Pilot `{d['pilot_commit']}`; manifest SHA-256 `{d['manifest_sha256']}`. Only four already selected plans/results were analyzed. No solver/E0/E1/E2 ran.",'','`mandatory_copy_work` counts boundary input/output, cross-tensor and cross-direct original COPYs before Step2 spill. `service_work` sums per-COPY max(1, ceil(size / 60)); it is an abstract service-work measure, **not an exact official makespan lower bound**. The separate per-tensor accounting counts each cross-core tensor pair as one OUT plus one IN.','', '| Cell | Selected | Old→new scheduled bytes | Added DDR Δ | COPY bytes old→new by category (BI / BO / tensor / direct) | Work old→new (same order) | zero-spill exact match? |','|---|---|---:|---:|---|---|---|']
    for r in d['cells']:
        o,n=r['old'],r['new']; ox,nx=r['old_E0'],r['new_E0']; cat=lambda q:'/'.join(str(q['categories'][c]['transfer_bytes']) for c in ('boundary_input','boundary_output','cross_tensor','cross_direct')); work=lambda q:'/'.join(str(q['categories'][c]['service_work']) for c in ('boundary_input','boundary_output','cross_tensor','cross_direct'))
        lines.append(f"| {r['case']}/k{r['cores']} | {r['selection']} | {ox['scheduled_copy_bytes']}→{nx['scheduled_copy_bytes']} | {nx['scheduled_copy_bytes']-ox['scheduled_copy_bytes']} | {cat(o)} → {cat(n)} | {work(o)} → {work(n)} | {r['zero_spill_copy_match']['old']}/{r['zero_spill_copy_match']['new']} |")
    by={r['case']:r for r in d['cells']}
    lines+=['','## Interpretation','',f"003/k2 adds {by['003']['new_E0']['scheduled_copy_bytes']-by['003']['old_E0']['scheduled_copy_bytes']:,} scheduled bytes: boundary input +{by['003']['new']['categories']['boundary_input']['transfer_bytes']-by['003']['old']['categories']['boundary_input']['transfer_bytes']:,}, cross-tensor +{by['003']['new']['categories']['cross_tensor']['transfer_bytes']:,}; boundary output and direct edges are unchanged/zero. This is spread across {d['tensor_concentration']['003-k2']['increased_tensor_count']:,} tensors and {d['cross_tensor_pair_deltas']['003-k2']['new_pair_count']:,} core-pair cuts; the ten largest account for {d['tensor_concentration']['003-k2']['top10_positive_delta_bytes']/d['tensor_concentration']['003-k2']['positive_pair_delta_bytes']:.1%} of positive cross-tensor growth.",f"056/k5 adds {by['056']['new_E0']['scheduled_copy_bytes']-by['056']['old_E0']['scheduled_copy_bytes']:,} bytes: boundary input +{by['056']['new']['categories']['boundary_input']['transfer_bytes']-by['056']['old']['categories']['boundary_input']['transfer_bytes']:,}, cross-tensor +{by['056']['new']['categories']['cross_tensor']['transfer_bytes']:,}; output/direct unchanged/zero. Growth spans {d['tensor_concentration']['056-k5']['increased_tensor_count']:,} tensors and {d['cross_tensor_pair_deltas']['056-k5']['new_pair_count']:,} core-pair cuts; top ten are {d['tensor_concentration']['056-k5']['top10_positive_delta_bytes']/d['tensor_concentration']['056-k5']['positive_pair_delta_bytes']:.1%} of growth. Thus neither case's DDR increase is concentrated in a few tensors; many split tensors could be co-location candidates, but no specific merge is certified to preserve Makespan, legality, or spill behavior.",'','Per-cell tensor-pair contributions are in `diagnosis.json`; top-ten entries include tensor IDs and source/destination cores. This is structural diagnosis, not causal proof about observed Makespan.','', '## Source limits','','Inputs and SHA checks are recorded in `diagnosis.json`; baseline plan/truth bytes come from the manifest-pinned Git commit and graph/selected archives from the pilot commit. No graph or source files were changed. No scheduleStep or lower-bound API was run.']
    (OUT/'SUMMARY.md').write_text('\n'.join(lines)+'\n')
if __name__=='__main__': main()
