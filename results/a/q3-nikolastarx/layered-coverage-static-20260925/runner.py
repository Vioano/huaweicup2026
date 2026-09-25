#!/usr/bin/env python3
"""One-process structural coverage audit; no plan construction or evaluation."""
import datetime, hashlib, json, signal, subprocess, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
class GlobalTimeout(Exception): pass
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def utc(): return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='microseconds').replace('+00:00','Z')
def timeout_handler(signum, frame): raise GlobalTimeout('60-second total audit timeout')
def main():
    out=Path(__file__).resolve().parent; mp=out/'manifest.json'; m=json.loads(mp.read_text())
    if subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()!=m['frozen_commit']: raise SystemExit('frozen HEAD mismatch')
    if sha(ROOT/m['source_path'])!=m['source_sha256']: raise SystemExit('frozen source SHA mismatch')
    if sha(out/'runner.py')!=m['runner_sha256']: raise SystemExit('frozen runner SHA mismatch')
    if (out/'run_claim.json').exists() or (out/'coverage.jsonl').exists() or (out/'run_summary.json').exists(): raise SystemExit('prior claim/output exists; refuse rerun')
    for c in m['cases']:
        if sha(ROOT/c['graph'])!=c['graph_sha256']: raise SystemExit(f"{c['case_id']} input SHA mismatch")
    import sys; sys.path.insert(0,str(ROOT/'data/raw/a/official/code')); sys.path.insert(0,str(ROOT))
    import src.q3.layered_query_flow as alg
    from src.q3.attention_rows import _ports,_recognize
    summary={'id':m['id'],'frozen_commit':m['frozen_commit'],'source_sha256':m['source_sha256'],'started_at':utc(),'status':'running','processed':0,'unsupported':0,'unexpected_exception':None,'timeout':False,'official_calls':{'Task':0,'Step':0,'E0':0,'E1':0,'E2':0,'pipe_bound':0}}
    (out/'run_claim.json').write_text(json.dumps({'claimed_at':summary['started_at'],'pid':__import__('os').getpid(),'manifest_sha256':sha(mp),'runner_sha256':sha(out/'runner.py')},indent=2)+'\n')
    signal.signal(signal.SIGALRM,timeout_handler); signal.setitimer(signal.ITIMER_REAL,m['budget']['total_seconds'])
    with (out/'coverage.jsonl').open('w') as log:
      for c in m['cases']:
        start=utc(); t0=time.monotonic(); stage='json_load'; row={'case_id':c['case_id'],'graph_sha256':c['graph_sha256'],'started_at':start}
        try:
          graph=json.loads((ROOT/c['graph']).read_text(encoding='utf-8'))
          stage='RawIndex.build'; index=alg.RawIndex.build(graph); row['op_count']=len(index.ops)
          stage='_ports'; ports=_ports(index)
          stage='recognize_layers'; rows,depth,keys,labels,kv,qsucc=alg.recognize_layers(index,ports,_recognize)
          row['row_count']=len(rows); row['layer_count']=1+max(depth.values()) if depth else 0
          stage='decompose'; tracks,private,parts,phase,up,down,anchors,signatures=alg.decompose(index,labels,kv)
          row['track_count']=len(tracks); row['shared_component_count']=len(parts); row['shared_op_count']=sum(map(len,parts)); row['track_sizes']=[len(t) for t in tracks]; row['private_op_count']=len(private)
          row['r_5core_dp_necessary_condition']=bool(5<=len(tracks)<=10); row['status']='recognized_and_decomposed'; row['unsupported_reason']=None
        except alg.UnsupportedStructure as e: row.update({'status':'unsupported_structure','unsupported_stage':stage,'unsupported_reason':str(e)})
        except GlobalTimeout as e:
          row.update({'status':'timeout','unsupported_stage':stage,'error':str(e),'finished_at':utc(),'wall_seconds':time.monotonic()-t0}); summary['timeout']=True; log.write(json.dumps(row,ensure_ascii=False)+'\n'); log.flush(); break
        except Exception as e:
          row.update({'status':'unexpected_exception','exception_type':type(e).__name__,'stage':stage,'error':str(e),'finished_at':utc(),'wall_seconds':time.monotonic()-t0}); log.write(json.dumps(row,ensure_ascii=False)+'\n'); log.flush(); summary['processed']+=1; summary['unexpected_exception']={'case_id':c['case_id'],'stage':stage,'type':type(e).__name__,'error':str(e)}; break
        row['finished_at']=utc(); row['wall_seconds']=time.monotonic()-t0; log.write(json.dumps(row,ensure_ascii=False)+'\n'); log.flush(); summary['processed']+=1
        if row['status']=='unsupported_structure': summary['unsupported']+=1
        summary['last_case']=c['case_id']; (out/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    signal.setitimer(signal.ITIMER_REAL,0); summary['finished_at']=utc()
    if summary['timeout']: summary['status']='timeout'
    elif summary['unexpected_exception']: summary['status']='stopped_unexpected_exception'
    else: summary['status']='complete' if summary['processed']==100 else 'incomplete'
    summary['elapsed_seconds']=(datetime.datetime.fromisoformat(summary['finished_at'].replace('Z','+00:00'))-datetime.datetime.fromisoformat(summary['started_at'].replace('Z','+00:00'))).total_seconds()
    (out/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:summary.get(k) for k in ['status','processed','unsupported','elapsed_seconds','official_calls','unexpected_exception']},ensure_ascii=False))
    return 0 if summary['status']=='complete' else 1
if __name__=='__main__': raise SystemExit(main())
