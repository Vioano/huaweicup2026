"""Rebuild the exact frozen input bundle from Git; no installs or probe execution."""
from pathlib import Path
import argparse,gzip,hashlib,io,json,subprocess,tarfile,zipfile
HERE=Path(__file__).resolve().parent
SOURCE='030f2b8aff4dc5e6b1acf9d88dc4984e54f1b5fa'
EXPECTED='49550ba410f732c2cc4032adca58765f33f76685a642280039455a18a958abb5'
def build(repo,output):
 if output.exists():raise FileExistsError(output)
 manifest_raw=(HERE/'bundle-manifest.json').read_bytes()
 manifest=json.loads(manifest_raw)
 if manifest['source_commit']!=SOURCE:raise ValueError('wrong manifest source')
 def blob(path):return subprocess.check_output(['git','show',SOURCE+':'+path],cwd=repo)
 contents={}
 for row in manifest['files']:
  name=row['path']
  path=Path(name)
  if path.is_absolute() or '..' in path.parts:raise ValueError('unsafe path')
  if name=='case_008.json':
   official=json.loads(blob('docs/a/source-manifest.json'))
   with zipfile.ZipFile(io.BytesIO(blob(official['case_archive']['path']))) as z:
    raw=z.read('data/case_008.json')
  else:raw=blob(name)
  if len(raw)!=row['bytes'] or hashlib.sha256(raw).hexdigest()!=row['sha256']:raise ValueError('source mismatch: '+name)
  contents[name]=raw
 contents['bundle-manifest.json']=manifest_raw
 rawtar=io.BytesIO()
 with tarfile.open(fileobj=rawtar,mode='w',format=tarfile.PAX_FORMAT) as tf:
  for name,raw in sorted(contents.items()):
   item=tarfile.TarInfo(name);item.size=len(raw);item.mode=0o644
   tf.addfile(item,io.BytesIO(raw))
 encoded=io.BytesIO()
 with gzip.GzipFile(filename='',fileobj=encoded,mode='wb',mtime=0,compresslevel=9) as gf:gf.write(rawtar.getvalue())
 raw=encoded.getvalue()
 if hashlib.sha256(raw).hexdigest()!=EXPECTED:raise ValueError('reconstructed archive SHA differs; do not run')
 with output.open('xb') as f:f.write(raw)
 return {'files':len(contents)-1,'bytes':len(raw),'sha256':EXPECTED}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repo',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 print(json.dumps(build(a.repo,a.output)))
if __name__=='__main__':main()
