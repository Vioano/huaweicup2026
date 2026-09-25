"""One fixed-owner reverse retiming; no evaluator call."""
import argparse, json, sys, time
from pathlib import Path

p=argparse.ArgumentParser()
for n in ('graph','config','incumbent','output','detail','official_code'): p.add_argument('--'+n,required=True,type=Path)
a=p.parse_args()
sys.path.insert(0,str(Path(__file__).absolute().parents[2]))
sys.path.insert(0,str(a.official_code))
from evaluation_validation import read_evaluation_config
from multicore_cut_evaluate_problem_2 import read_scene_b_config
from src.q2_nikolastarx.fixed_owner_reverse import retime
started=time.perf_counter()
graph=json.loads(a.graph.read_bytes()); incumbent=json.loads(a.incumbent.read_bytes())
config={**read_evaluation_config(a.config),**read_scene_b_config(a.config)}
new,detail=retime(graph,incumbent,config)
with a.output.open('x') as f: json.dump(new,f,separators=(',',':')); f.write('\n')
detail['read_to_plan_seconds']=time.perf_counter()-started
with a.detail.open('x') as f: json.dump(detail,f,indent=2); f.write('\n')
