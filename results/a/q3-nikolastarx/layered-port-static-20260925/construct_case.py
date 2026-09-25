#!/usr/bin/env python3
"""Single pure-constructor child. No official simulation/evaluator calls."""
import argparse, json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT/'data/raw/a/official/code')); sys.path.insert(0,str(ROOT))
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
from src.q3.layered_query_flow import construct_layered
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--case'); ap.add_argument('--graph'); ap.add_argument('--config'); ap.add_argument('--out'); ap.add_argument('--capacity'); ap.add_argument('--delay',type=int); a=ap.parse_args()
    cap=json.loads(a.capacity); actual=read_evaluation_config(a.config)['capacity']; delay=read_scene_b_config(a.config)['cross_core_copy_delay_cycles']
    if cap!=actual or delay!=a.delay: raise RuntimeError(f'config mismatch requested={cap}/{a.delay} actual={actual}/{delay}')
    graph=json.loads(Path(a.graph).read_text(encoding='utf-8'))
    plan,metadata,evidence=construct_layered(graph,5,capacity=cap,cross_delay_cycles=delay)
    out=Path(a.out); out.mkdir(parents=True,exist_ok=False)
    (out/'plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'metadata.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'evidence.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'constructed','case_id':a.case,'official_calls':metadata['official_calls'],'out':str(out.relative_to(ROOT))},ensure_ascii=False))
if __name__=='__main__': main()
