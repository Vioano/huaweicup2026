"""Create a minimal frozen E0 package; requires later pinned runner commit."""
import argparse,gzip,hashlib,io,json,pathlib,subprocess,tarfile
ROOT=pathlib.Path(__file__).resolve().parents[4]
GRAPH_ARCHIVE=ROOT/'results/a/p1-coalesced-phase-colab-20260925/preflight/coalesced-source-bundle.tar.gz'
DATA_HEAD='a008dfb8f1b5b881844af312be0b7246b2c6b025'
GRAPH_SHA='c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d'
SOURCE_MANIFEST_SHA='713792d81693757a71cb29b9daea7434192d1bf14fcb8efd25165e6f68d9cffc'
CONFIG_SHA='dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9'
EVALUATOR_SHA='2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f'
PLAN='results/a/p1-coalesced-phase-colab-20260925/run-0738Z/workspace/evidence/coalesced-008-k5/phase-plan.json'
PLAN_SHA='e9327269bc95a81d17ca907a617aed896fd6fdde2a3174044d975f746569f9ce'
def sha(b):return hashlib.sha256(b).hexdigest()
def archive(commit,paths):
 data=subprocess.run(['git','-C',str(ROOT),'archive','--format=tar',commit,*paths],capture_output=True,check=True).stdout;out={}
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:') as tf:
  for m in tf.getmembers():
   if not m.isfile():continue
   q=pathlib.PurePosixPath(m.name)
   if q.is_absolute() or '..' in q.parts:raise ValueError('unsafe git path')
   out[m.name]=tf.extractfile(m).read()
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('--runner-commit',required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 files=archive(DATA_HEAD,['data/raw/a/official/code','data/raw/a/official/data/config.txt','docs/a/source-manifest.json',PLAN])
 plan=files.pop(PLAN);files['phase-plan.json']=plan
 files.update(archive(a.runner_commit,['pyproject.toml','uv.lock','.python-version','src/q1_benchmarks/bounded_probe_e0.py','src/review/p1_saved_plan_e0_once.py']))
 with tarfile.open(GRAPH_ARCHIVE,'r:gz') as tf:graph=tf.extractfile('case_008.json').read()
 if sha(graph)!=GRAPH_SHA or sha(files['phase-plan.json'])!=PLAN_SHA:raise ValueError('frozen graph/plan mismatch')
 assert sha(files['docs/a/source-manifest.json'])==SOURCE_MANIFEST_SHA
 sm=json.loads(files['docs/a/source-manifest.json']);smf={x['path']:x for x in sm['files']}
 for rel,row in smf.items():
  if rel.startswith('code/') or rel=='data/config.txt':
   b=files['data/raw/a/official/'+rel];assert len(b)==row['bytes'] and sha(b)==row['sha256']
 agg=hashlib.sha256()
 for rel,row in sorted(smf.items()):
  if rel.startswith('code/'):agg.update(rel.encode()+b'\t'+row['sha256'].encode()+b'\n')
 assert agg.hexdigest()==sm['official_code_hash']=='de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0'
 assert sha(files['data/raw/a/official/data/config.txt'])==CONFIG_SHA and sha(files['data/raw/a/official/code/multicore_cut_evaluate_problem_1.py'])==EVALUATOR_SHA
 files['case_008.json']=graph;rows=[{'path':k,'bytes':len(v),'sha256':sha(v)} for k,v in sorted(files.items())]
 manifest={'status':'frozen-minimal-e0-package','data_head':DATA_HEAD,'runner_commit':a.runner_commit,'plan_sha256':PLAN_SHA,'graph_sha256':GRAPH_SHA,'official_code_hash':sm['official_code_hash'],'config_sha256':sha(files['data/raw/a/official/data/config.txt']),'files':rows}
 files['bundle-manifest.json']=(json.dumps(manifest,indent=2)+'\n').encode();a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('xb') as raw:
  with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as gz:
   with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as tf:
    for n,b in sorted(files.items()):
     i=tarfile.TarInfo(n);i.size=len(b);i.mtime=0;i.mode=0o644;i.uid=i.gid=0;i.uname=i.gname='';tf.addfile(i,io.BytesIO(b))
 print(json.dumps({'files':len(rows),'bytes':a.output.stat().st_size,'sha256':sha(a.output.read_bytes())}))
if __name__=='__main__':main()
