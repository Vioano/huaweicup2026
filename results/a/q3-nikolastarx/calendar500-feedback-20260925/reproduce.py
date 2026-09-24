#!/usr/bin/env python3
"""Compare existing expanded/calendar P3 feeds; no scoring or evaluator calls."""
import argparse, csv, gzip, hashlib, json
from pathlib import Path


def load(path): return json.loads(Path(path).read_text())['records']
def sha(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--old-root',required=True,help='expanded producer checkout')
    ap.add_argument('--new-root',required=True,help='calendar producer checkout')
    ap.add_argument('--old-feed',required=True); ap.add_argument('--new-feed',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args(); old,new=load(a.old_feed),load(a.new_feed)
    def index(rows):
        out={}
        for r in rows:
            key=(r['case_id'],int(r['cores']))
            if key in out: raise ValueError(f'duplicate coordinate {key}')
            if r['status']!='ok' or r['problem']!='P3': raise ValueError(f'non-ok/non-P3 {key}')
            out[key]=r
        return out
    oi,ni=index(old),index(new); expected={(f'{i:03}',k) for i in range(1,101) for k in range(1,6)}
    if set(oi)!=expected or set(ni)!=expected: raise ValueError('feed is not exact 100x5 coverage')
    if {r['solver_commit'] for r in new}!={'8314351854c716091bc6d31215569825ae45ec55'}: raise ValueError('new feed source differs')
    if {r['solver_commit'] for r in old}!={'a5dafdf94d0694132fb9ec7121f5fe1fe0d6ee3b'}: raise ValueError('old feed source differs')
    calls={k:sum(r['provenance']['measurement']['calls'][k] for r in new) for k in ('solver','E0','E1','E2')}
    if calls!={'solver':500,'E0':861,'E1':0,'E2':0}: raise ValueError('call ledger totals differ')
    rows=[]; baseline_checks={}
    for key in sorted(expected):
        x,y=oi[key],ni[key]
        for field in ('graph_sha256','config_sha256','official_sha256'):
            if x['identity'][field]!=y['identity'][field]: raise ValueError(f'{field} mismatch {key}')
        for r,root,label in ((x,a.old_root,'old'),(y,a.new_root,'new')):
            b=r['baseline']; ident=r['identity']
            for f in ('graph_sha256','config_sha256','official_sha256'):
                if b[f]!=ident[f]: raise ValueError(f'{label} baseline {f} mismatch {key}')
            if b['route']!='E0' or b['entrypoint']!='singlecore_evaluate.evaluate_singlecore': raise ValueError(f'baseline evaluator mismatch {key}')
            p=Path(root)/b['result']['path']
            if sha(p)!=b['result']['sha256']: raise ValueError(f'baseline gzip SHA mismatch {label} {key}')
            d=json.load(gzip.open(p,'rt'))
            if d.get('scene')!='A' or d.get('num_cores')!=1: raise ValueError(f'baseline scene/core mismatch {label} {key}')
            if d.get('makespan') is None or int(d['makespan'])<=0: raise ValueError(f'baseline M missing {label} {key}')
            baseline_checks.setdefault(key[0],[]).append((label,int(d['makespan']),b['result']['sha256']))
        if x['baseline']['result']['sha256']!=y['baseline']['result']['sha256']: raise ValueError(f'baseline source differs {key}')
        bpath=Path(a.new_root)/y['baseline']['result']['path']; bd=json.load(gzip.open(bpath,'rt')); bm=int(bd['makespan'])
        xm=int(x['metrics']['makespan_cycles']); ym=int(y['metrics']['makespan_cycles'])
        rows.append({'case_id':key[0],'cores':key[1],'old_makespan':xm,'calendar_makespan':ym,'baseline_makespan':bm,'old_speedup':bm/xm,'calendar_speedup':bm/ym,'m_change':('improved' if ym<xm else 'regressed' if ym>xm else 'equal'),'old_solver_wall_s':x['metrics']['solver_wall_seconds'],'calendar_solver_wall_s':y['metrics']['solver_wall_seconds'],'old_extra_ddr_bytes':x['metrics']['extra_ddr_bytes'],'calendar_extra_ddr_bytes':y['metrics']['extra_ddr_bytes'],'old_spill_bytes':x['metrics']['spill_bytes'],'calendar_spill_bytes':y['metrics']['spill_bytes'],'old_cache_hit_rate':x['metrics']['cache_hit_rate'],'calendar_cache_hit_rate':y['metrics']['cache_hit_rate']})
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    with (out/'cells.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator="\n");w.writeheader();w.writerows(rows)
    summary=[]
    for k in range(1,6):
        q=[r for r in rows if r['cores']==k]; n=len(q)
        summary.append({'cores':k,'n':n,'old_mean_speedup':sum(r['old_speedup'] for r in q)/n,'calendar_mean_speedup':sum(r['calendar_speedup'] for r in q)/n,'improved':sum(r['m_change']=='improved' for r in q),'equal':sum(r['m_change']=='equal' for r in q),'regressed':sum(r['m_change']=='regressed' for r in q),'calendar_solver_wall_mean_s':sum(r['calendar_solver_wall_s'] for r in q)/n,'calendar_solver_wall_max_s':max(r['calendar_solver_wall_s'] for r in q),'old_extra_ddr_sum':sum(r['old_extra_ddr_bytes'] for r in q),'calendar_extra_ddr_sum':sum(r['calendar_extra_ddr_bytes'] for r in q),'old_spill_sum':sum(r['old_spill_bytes'] for r in q),'calendar_spill_sum':sum(r['calendar_spill_bytes'] for r in q),'old_mean_cache_hit_rate':sum(r['old_cache_hit_rate'] for r in q)/n,'calendar_mean_cache_hit_rate':sum(r['calendar_cache_hit_rate'] for r in q)/n})
    json.dump({'old_records':len(old),'calendar_records':len(new),'fixed_calendar_solver_commit':new[0]['solver_commit'],'old_solver_commit':old[0]['solver_commit'],'old_feed_sha256':sha(a.old_feed),'new_feed_sha256':sha(a.new_feed),'calls':calls,'baseline_cases_verified':100,'baseline_scene':'A','baseline_cores':1,'baseline_sha_match_all_cases':True,'by_core':summary,'note':'Speedup is per-case single-core baseline makespan divided by multicore makespan, arithmetic mean. Independent metrics are reported separately; no composite dominance claim.'},(out/'summary.json').open('w'),indent=2)
if __name__=='__main__': main()
