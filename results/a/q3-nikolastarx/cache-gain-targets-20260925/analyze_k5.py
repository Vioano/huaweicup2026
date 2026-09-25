#!/usr/bin/env python3
"""One-shot, K5-only metric readback from pinned forest and P2 artifacts."""
import csv, gzip, hashlib, json, os, subprocess, sys
from pathlib import Path

ROOT = Path.cwd()
OUT = ROOT / "results/a/q3-nikolastarx/cache-gain-targets-20260925"
INDEX = ROOT / "results/a/q3-nikolastarx/forest-cachepair-delta-20260925/manifest.json"
RUN_DELTA = ROOT / "results/a/q3-nikolastarx/forest-cachepair-delta-20260925/20260924T2205Z-s3172/run.json"
ART = "bff88a66cd76ceb2d75242bf99d34bfe8b1879d4"
BASEART = "19bebf35205d23fdd832781540f8879da52eeb62"
P2ART = "11d5d3ba1820864626bb49acccbeec7a75553e80"
SOLVER = "311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1"
BASE = "results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee"
FOREST_AUDIT = ROOT / "results/a/q3-nikolastarx/forest-full500-feedback-20260925/independent-audit.json"
PAIR_AUDIT = ROOT / "results/a/q3-nikolastarx/forest-cachepair-delta-20260925/independent-audit.json"
P2_PREFIX = "results/a/q3-nikolastarx/witness-cachepair-20260925-s59/20260924T2102Z-s59ee/cells/"
LAYERED = {"005","009","040","047","049","053","069","071","072","075","082","085","086"}

def sha(b): return hashlib.sha256(b).hexdigest()
def git_bytes(commit, path):
    return subprocess.run(["git","show",f"{commit}:{path}"],check=True,capture_output=True,timeout=15).stdout
def read_json_bytes(b, gz=False): return json.loads(gzip.decompress(b) if gz else b)
def get_index(): return json.loads(INDEX.read_text())
def all_k5(d):
    rows=[r for r in d["records"] if r["cores"]==5]
    assert len(rows)==100 and len({r["case_id"] for r in rows})==100
    assert {r["case_id"] for r in rows}=={f"{i:03d}" for i in range(1,101)}
    assert all(r["official_sha256"]=="de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0" for r in rows)
    return sorted(rows,key=lambda r:r["case_id"])
def p2_path(r):
    if r["action"]=="reuse_existing_p2":
        return ("git", P2ART, P2_PREFIX+f"{r['case_id']}-k5/result.json.gz")
    assert r["action"]=="requires_new_p2_e0"
    return ("disk", None, str(ROOT/"results/a/q3-nikolastarx/forest-cachepair-delta-20260925/20260924T2205Z-s3172/cells"/Path(f"{r['case_id']}-k5/result.json.gz")))
def raw(src):
    kind,commit,path=src
    return git_bytes(commit,path) if kind=="git" else Path(path).read_bytes()
def p3_path(r): return f"{BASE}/{r['forest_p3_result'].split('/20260924T2122Z-s59ee/',1)[1]}"
def plan_path(r): return f"{BASE}/{r['forest_plan']['path'].split('/20260924T2122Z-s59ee/',1)[1]}"
def baseline_path(r): return f"{BASE}/revision2-baseline-draft/baseline/{r['case_id']}/result.json.gz"

def freeze():
    d=get_index(); rows=all_k5(d)
    assert d["sources"]["forest_artifact_commit"]==ART and d["sources"]["p2_result_artifact_commit"]==P2ART
    dispatch=json.loads(git_bytes(ART,f"{BASE}/dispatch.json"))
    assert dispatch["source_commit"]==SOLVER and dispatch["status"]=="complete"
    delta=json.loads(RUN_DELTA.read_text()); assert delta["status"]=="complete" and delta["new_p2_e0_succeeded"]==24
    inv=[]
    for r in rows:
        # Resolve and hash only this K5 plan, P3 result, same-plan P2 result, and M1 baseline.
        plan=git_bytes(ART,plan_path(r)); assert sha(plan)==r["forest_plan"]["sha256"]
        p3p=p3_path(r); p3=git_bytes(ART,p3p)
        runp=p3p.rsplit("/evidence/result.json.gz",1)[0]+"/run.json"
        run=json.loads(git_bytes(ART,runp))
        assert run["status"]=="ok" and run["calls"]["solver"]==1
        assert run["artifacts"]["result"]["sha256"]==sha(p3)
        assert run["artifacts"]["plan"]["sha256"]==r["forest_plan"]["sha256"]
        psrc=p2_path(r); p2=raw(psrc)
        if r["action"]=="reuse_existing_p2":
            assert sha(p2)==r["reused_p2"]["sha256"]
            assert r["reused_p2"]["source_plan_sha256"]==r["forest_plan"]["sha256"]
        else:
            job=next(j for j in delta["jobs"] if j["coordinate"]==f"{r['case_id']}-k5")
            assert job["status"]=="ok" and job["plan_sha256"]==r["forest_plan"]["sha256"] and job["result_sha256"]==sha(p2)
        bpath=baseline_path(r); b=git_bytes(BASEART,bpath)
        inv.append({"case_id":r["case_id"],"cores":5,"action":r["action"],"plan_sha256":sha(plan),"graph_sha256":r["graph_sha256"],"config_sha256":r["config_sha256"],"official_sha256":r["official_sha256"],"p3_path":p3p,"p3_sha256":sha(p3),"p2_source":psrc[0]+":"+(psrc[1]+":" if psrc[1] else "")+psrc[2],"p2_sha256":sha(p2),"baseline_path":bpath,"baseline_sha256":sha(b)})
    freeze_doc={"scope":"K5 only; 100 unique cases; same forest plan bytes for no-L2/Cache pair; same complete forest solver batch; no trace read","forest_p3_artifact_commit":ART,"official_singlecore_artifact_commit":BASEART,"p2_artifact_commit":P2ART,"forest_acceptance_audit_sha256":sha(FOREST_AUDIT.read_bytes()),"cachepair_audit_sha256":sha(PAIR_AUDIT.read_bytes()),"solver_commit":SOLVER,"forest_cachepair_manifest_sha256":sha(INDEX.read_bytes()),"cachepair_delta_run_sha256":sha(RUN_DELTA.read_bytes()),"dispatch_sha256":sha(git_bytes(ART,f"{BASE}/dispatch.json")),"dispatch_status":dispatch["status"],"k5_rows":100,"row_inventory":inv,"statistics":"G=M2/M3. Report median/min/max of G; nonoverlap bins: G<1, G=1, 1<G<1.01, 1.01<=G<1.1, 1.1<=G<1.25, 1.25<=G<1.5, 1.5<=G<2, G>=2; means are per-case arithmetic means; baseline speedup=mean(M1/M3); proportional reduction=mean(1-M3/M2). Diagnose ten lowest G, carrying M3 and M1 for workload context; label supplied 13 layered candidates."}
    (OUT/"FROZEN_INPUTS.json").write_text(json.dumps(freeze_doc,indent=2)+"\n")
    print(json.dumps({k:freeze_doc[k] for k in ["forest_p3_artifact_commit","official_singlecore_artifact_commit","p2_artifact_commit","solver_commit","forest_cachepair_manifest_sha256","cachepair_delta_run_sha256","k5_rows"]},indent=2))

def stats():
    frozen=json.loads((OUT/"FROZEN_INPUTS.json").read_text()); d=get_index(); rows=all_k5(d)
    assert sha(INDEX.read_bytes())==frozen["forest_cachepair_manifest_sha256"] and len(rows)==100
    assert sha(FOREST_AUDIT.read_bytes())==frozen["forest_acceptance_audit_sha256"] and sha(PAIR_AUDIT.read_bytes())==frozen["cachepair_audit_sha256"]
    assert sha(RUN_DELTA.read_bytes())==frozen["cachepair_delta_run_sha256"]
    data=[]
    for r,fr in zip(rows,frozen["row_inventory"]):
        assert r["case_id"]==fr["case_id"]
        p3p=p3_path(r); p3b=git_bytes(ART,p3p); p2b=raw(p2_path(r)); bb=git_bytes(BASEART,baseline_path(r))
        assert [sha(p3b),sha(p2b),sha(bb)]==[fr["p3_sha256"],fr["p2_sha256"],fr["baseline_sha256"]]
        m3=read_json_bytes(p3b,True)["makespan"]; m2=read_json_bytes(p2b,True)["makespan"]; m1=read_json_bytes(bb,True)["makespan"]
        g=m2/m3
        data.append({"case_id":r["case_id"],"M1":m1,"M2_noL2":m2,"M3_cache":m3,"G_M2_over_M3":g,"baseline_over_M3":m1/m3,"fractional_reduction_1_minus_M3_over_M2":1-m3/m2,"layered_candidate":r["case_id"] in LAYERED,"plan_sha256":fr["plan_sha256"],"graph_sha256":fr["graph_sha256"]})
    gs=sorted(x["G_M2_over_M3"] for x in data)
    bins=[("G<1",lambda g:g<1),("G=1",lambda g:g==1),("1<G<1.01",lambda g:1<g<1.01),("1.01<=G<1.1",lambda g:1.01<=g<1.1),("1.1<=G<1.25",lambda g:1.1<=g<1.25),("1.25<=G<1.5",lambda g:1.25<=g<1.5),("1.5<=G<2",lambda g:1.5<=g<2),("G>=2",lambda g:g>=2)]
    def mean(k): return sum(x[k] for x in data)/len(data)
    summary={"n":len(data),"solver_commit":SOLVER,"artifact_commit":ART,"baseline_artifact_commit":BASEART,"median_G":(gs[49]+gs[50])/2,"min_G":gs[0],"max_G":gs[-1],"arithmetic_mean_G":mean("G_M2_over_M3"),"mean_fractional_reduction":mean("fractional_reduction_1_minus_M3_over_M2"),"mean_official_singlecore_speedup_M1_over_M3":mean("baseline_over_M3"),"G_distribution":{name:sum(fn(x["G_M2_over_M3"]) for x in data) for name,fn in bins},"note":"These K5 descriptive statistics diagnose the fixed forest algorithm; they are not new solver/evaluator results or a future-potential estimate.","low_G_top10_order":"ascending G; ties by case id"}
    top=sorted(data,key=lambda x:(x["G_M2_over_M3"],x["case_id"]))[:10]
    (OUT/"k5-cell-metrics.csv").write_text("")
    with (OUT/"k5-cell-metrics.csv").open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=list(data[0].keys())); w.writeheader(); w.writerows(data)
    (OUT/"k5-summary.json").write_text(json.dumps(summary,indent=2)+"\n")
    (OUT/"k5-low-g-top10.json").write_text(json.dumps(top,indent=2)+"\n")
    print(json.dumps({"summary":summary,"low_g_top10":top},indent=2))

if __name__=="__main__":
    if len(sys.argv)!=2 or sys.argv[1] not in {"freeze","stats"}: raise SystemExit("usage: analyze_k5.py freeze|stats")
    (freeze if sys.argv[1]=="freeze" else stats)()
