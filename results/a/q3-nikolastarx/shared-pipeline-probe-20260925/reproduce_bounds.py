"""Recompute the fixed pipeline-family ceiling, without any evaluator calls."""
import argparse,csv,hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(ROOT))
from src.q3.construct import Index
from src.q3.shared_pipeline import construct
from src.q3.pipe_bound import analyze
SOURCE="87f677f8f16e31a71c071d49dd176d4420efb36d"
def main():
    ap=argparse.ArgumentParser();ap.add_argument("--output",type=Path,required=True);a=ap.parse_args()
    for name in ("construct","shared_pipeline","pipe_bound"):
        rel=f"src/q3/{name}.py"
        if (ROOT/rel).read_bytes()!=subprocess.check_output(["git","show",f"{SOURCE}:{rel}"],cwd=ROOT):
            raise ValueError("fixed constructor/bound source differs: "+rel)
    folder=Path(__file__).resolve().parent
    census=json.loads((folder/"static-census.json").read_text())["accepted"]
    with (folder.parent/"calendar500-feedback-20260925/cells.csv").open() as f:
        old={(r["case_id"],int(r["cores"])):r for r in csv.DictReader(f)}
    rows=[]
    for item in census:
        c=item["case"].removeprefix("case_")
        raw=(ROOT/f"data/raw/a/official/data/case_{c}.json").read_bytes()
        index=Index(json.loads(raw))
        for k in range(2,6):
            plan,_=construct(index,k)
            lower=analyze(index.graph,plan,500)["with_cross_core_delay"]["lower_bound_cycles"]
            b=int(old[c,k]["baseline_makespan"]);m=int(old[c,k]["calendar_makespan"])
            rows.append(dict(case_id=c,cores=k,graph_sha256=hashlib.sha256(raw).hexdigest(),incumbent_M=m,candidate_LB=lower,pruned=lower>=m,incumbent_speedup=b/m,candidate_max_possible_speedup=b/lower,possible_gain_upper_bound=max(0,b/lower-b/m)))
    summary=[]
    for k in range(2,6):
        r=[x for x in rows if x["cores"]==k]
        mean=sum(float(v["calendar_speedup"]) for (_,c),v in old.items() if c==k)/100
        summary.append(dict(cores=k,candidates=len(r),bound_pruned=sum(x["pruned"] for x in r),remaining=sum(not x["pruned"] for x in r),current_mean=mean,candidate_family_mean_upper_bound=mean+sum(x["possible_gain_upper_bound"] for x in r)/100,target={2:2.28,3:3.23,4:4.09,5:4.76}[k]))
    original=json.loads((folder/"candidate-family-bound.json").read_text())
    if rows!=original["rows"] or summary!=original["by_core"]:
        raise ValueError("recomputed static ceiling differs from archived values")
    a.output.write_text(json.dumps(dict(source=SOURCE,rows=rows,by_core=summary,matched_archived=True,new_E0=0),indent=2)+"\n")
if __name__=="__main__":main()
