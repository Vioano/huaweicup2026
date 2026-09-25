"""No graph construction or evaluator; gate and pin checks only."""
import importlib.util,json,sys,tempfile
from datetime import datetime,timedelta,timezone
from pathlib import Path
h=Path(__file__).absolute().parent
spec=importlib.util.spec_from_file_location('probe',h/'run.py'); m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
d=m.load(h/'manifest.json')
class Args: pass
a=Args(); a.raw=Path('/Users/nikolastar/.codex/worktrees/q2-feedback-s8ee/huaweicup2026/data/raw/a/official'); a.python=Path(d['python_invocation'])
m.verify(a,d)
with tempfile.TemporaryDirectory() as td:
 g=Path(td)/'gate.json'; out=(Path(td)/'fresh').absolute()
 pins={'status':'admitted','scope':m.SCOPE,'manifest_sha256':m.sha(h/'manifest.json'),'runner_sha256':m.sha(h/'run.py'),'helper_sha256':m.sha(h/'construct.py'),'output_dir':str(out),'expires_at_utc':(datetime.now(timezone.utc)+timedelta(minutes=5)).isoformat()}
 def check(row,should_pass):
  g.write_text(json.dumps(row)); ok=True
  try:m.gate_check(g,pins['manifest_sha256'],pins['runner_sha256'],pins['helper_sha256'],out)
  except ValueError:ok=False
  assert ok==should_pass,(row,ok)
 check(pins,True)
 for key,bad in [('scope','wrong'),('status','pending'),('manifest_sha256','wrong'),('runner_sha256','wrong'),('helper_sha256','wrong'),('output_dir',str(out/'other')),('expires_at_utc','2000-01-01T00:00:00Z')]:check({**pins,key:bad},False)
 print(json.dumps({'status':'passed','source_files_verified':len(d['source_files']),'official_files_verified':len(d['official_files']),'cells':len(d['cells']),'gate_negative_cases':7,'construct_calls':0,'E0_calls':0}))
