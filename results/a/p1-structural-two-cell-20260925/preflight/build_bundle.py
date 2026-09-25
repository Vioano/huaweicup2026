"""Build a two-case package from the fixed solver commit; no run/score actions."""
import argparse,gzip,hashlib,io,json,pathlib,subprocess,tarfile,zipfile
ROOT=pathlib.Path(__file__).resolve().parents[4];SOLVER='3a1b82b71ca1ff6689eb8e72f17d26c48b52073c'
ARCHIVE=ROOT/'data/raw/a/official-cases.zip';ARCHIVE_SHA='e9c33753eb4c0caddc1ff8f05065144f762189d5071476611de1f7bb5887e528'
GRAPHS={'case_016.json':'76537aa7163cf0748adcff2ecbd84fbc9a02a2d129ffcecd2bfebb89685e71ef','case_024.json':'f974fbf1a23b4a145b5f8c9c691eb1b247f93d8785d98bb46a9cdd8626399aec'}
AUTHOR='AI chats/P1多Pipe链构造证明/附件/r1-p1_s6607/p1_phase_cut.py'
def sha(b):return hashlib.sha256(b).hexdigest()
def git_archive(paths):
 b=subprocess.run(['git','-C',str(ROOT),'archive','--format=tar',SOLVER,*paths],check=True,capture_output=True).stdout;out={}
 with tarfile.open(fileobj=io.BytesIO(b)) as tf:
  for m in tf.getmembers():
   if m.isfile():out[m.name]=tf.extractfile(m).read()
 return out
def main():
 p=argparse.ArgumentParser();p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 if sha(ARCHIVE.read_bytes())!=ARCHIVE_SHA:raise ValueError('official archive identity mismatch')
 files=git_archive(['.python-version','pyproject.toml','uv.lock','src/q1','src/q1_benchmarks/bounded_probe_e0.py','src/eval_exact','data/raw/a/official/code','data/raw/a/official/data/config.txt','docs/a/source-manifest.json',AUTHOR])
 if sha(files['src/q1_benchmarks/bounded_probe_e0.py'])!='08f86b1e95dbed9f0c3d82c4005cbf85d81e0164493fc4fc51542ced9035011c':raise ValueError('bounded process helper byte mismatch')
 files['src/review/p1_structural_two_cell_once.py']=(ROOT/'src/review/p1_structural_two_cell_once.py').read_bytes()
 with zipfile.ZipFile(ARCHIVE) as z:
  for name,digest in GRAPHS.items():
   case=name.removeprefix('case_').removesuffix('.json');raw=z.read(f'data/case_{case}.json')
   if sha(raw)!=digest:raise ValueError('case bytes mismatch '+case)
   files[name]=raw
 rows=[{'path':n,'bytes':len(b),'sha256':sha(b)} for n,b in sorted(files.items())]
 mf={'status':'two-cell-offline-package','solver_commit':SOLVER,'solver_path':'src/q1/structural_refine.py','official_archive_sha256':ARCHIVE_SHA,'graphs':GRAPHS,'files':rows}
 files['bundle-manifest.json']=(json.dumps(mf,indent=2,ensure_ascii=False)+'\n').encode();a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('xb') as raw:
  with gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as gz:
   with tarfile.open(fileobj=gz,mode='w',format=tarfile.PAX_FORMAT) as tf:
    for n,b in sorted(files.items()):
     ti=tarfile.TarInfo(n);ti.size=len(b);ti.mtime=0;ti.mode=0o644;ti.uid=ti.gid=0;ti.uname=ti.gname='';tf.addfile(ti,io.BytesIO(b))
 print(json.dumps({'files':len(rows),'bytes':a.output.stat().st_size,'sha256':sha(a.output.read_bytes()),'graphs':GRAPHS}))
if __name__=='__main__':main()
