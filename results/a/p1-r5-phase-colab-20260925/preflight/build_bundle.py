"""Build the R5 transport bundle only from a frozen Git commit and verified case bytes."""
import argparse, gzip, hashlib, io, json, pathlib, subprocess, tarfile
ROOT=pathlib.Path(__file__).resolve().parents[4]
PERIOD=ROOT/'results/a/p1-period7-colab-20260925/preflight/period7-source-bundle.tar.gz'
GRAPH='c93bb7ab5deec5112aff0cc001fbd76d001d3de5ea7463fba59b1f1ff2ba3e1d'
PATHS=['.python-version','pyproject.toml','uv.lock','src','data/raw/a/official',
 'AI chats/P1多Pipe链构造证明/附件/r5-P1_s6607_R5_causal_diagnosis/src','AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607']
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
 p=argparse.ArgumentParser();p.add_argument('--commit',required=True);p.add_argument('--graph-archive',type=pathlib.Path,default=PERIOD);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 subprocess.run(['git','-C',str(ROOT),'cat-file','-e',a.commit+'^{commit}'],check=True)
 source=subprocess.run(['git','-C',str(ROOT),'archive','--format=tar',a.commit,*PATHS],check=True,capture_output=True).stdout
 files={}
 with tarfile.open(fileobj=io.BytesIO(source),mode='r:') as src:
  for m in src.getmembers():
   if not m.isfile(): continue
   q=pathlib.PurePosixPath(m.name)
   if q.is_absolute() or '..' in q.parts: raise ValueError('unsafe git archive path')
   files[m.name]=src.extractfile(m).read()
 with tarfile.open(a.graph_archive,'r:gz') as old:
  graph=old.extractfile('case_008.json').read()
 if sha(graph)!=GRAPH:raise ValueError('period7 transfer does not contain frozen graph bytes')
 files['case_008.json']=graph
 rows=[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(files.items())]
 manifest={'status':'frozen-source-package','source_commit':a.commit,'source_paths':PATHS,'graph_sha256':GRAPH,'files':rows}
 files['bundle-manifest.json']=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
 a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('xb') as raw:
  with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as gz:
   with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as out:
    for n,b in sorted(files.items()):
     info=tarfile.TarInfo(n);info.size=len(b);info.mtime=0;info.mode=0o644;info.uid=info.gid=0;info.uname=info.gname=''
     out.addfile(info,io.BytesIO(b))
 print(json.dumps({'source_commit':a.commit,'graph_sha256':GRAPH,'files':len(rows),'bundle_bytes':a.output.stat().st_size,'bundle_sha256':sha(a.output.read_bytes())}))
if __name__=='__main__':main()
