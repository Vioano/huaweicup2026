import json
from pathlib import Path
from src.q3.convex_warmup_probe import decide,old_control
p=Path('results/a/q3-nikolastarx/convex-safe-one-shot-20260925/control.json')
d=json.loads(p.read_text());r=old_control(p,'dea9ae082ff0edeebc8c7014f7dfc8af36c893daab9617144c115e6b6eeb2b6f',graph_sha256=d['identity']['graph_sha256'],config_sha256=d['identity']['config_sha256'],official_code_sha256=d['identity']['official_sha256'])
assert r['M3']==24522 and r['M2']==29026
assert not decide(24522,None,r)['run_p2']
assert decide(24521,None,r)['run_p2']
assert decide(23000,29000,r)['accepted']
assert not decide(23000,29027,r)['accepted']
assert not decide(23500,28000,r)['accepted']
print(json.dumps({'control_exact':True,'decision_cases':5,'new_official_calls':0}))
