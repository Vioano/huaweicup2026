#!/usr/bin/env python3
"""Package the already reviewed paper checkpoint; no experiment execution."""
from pathlib import Path
import csv, hashlib, json, re, subprocess, zipfile
P=Path(__file__).resolve().parents[1]
O=P/'checkpoints/checkpoint-01'; B=P/'build/checkpoint-01'; T=P.parent/'template-2026'
figures=json.loads((O/'figure-manifest.json').read_text())
files={}
for name in ['anonymous-paper-v1.pdf','result-tables.pdf']:
    p=O/name
    info=subprocess.check_output(['pdfinfo',str(p)],text=True)
    files[name]={'pages':int(re.search(r'Pages:\s+(\d+)',info)[1]),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
for name in ['main','result-tables']:
    log=(B/(name+'.log')).read_text()
    warnings=re.findall(r'^.*(?:Overfull|Undefined|undefined|Missing character|too large|Warning).*$',log,flags=re.M)
    assert not warnings, warnings
rows=list(csv.DictReader((P/'data/all-results.csv').open()))
assert len(rows)==1500
for q in ['P1','P2','P3']:
    for k in range(1,6):
        assert len([r for r in rows if r['problem']==q and int(r['cores'])==k])==100
receipt={'date':'2026-09-26','stage':'complete anonymous review checkpoint, not final submission acceptance','files':files,'figures':len(figures),'data_rows':len(rows),'compile_warning_checks':'passed','new_solver_and_evaluator_calls':0,'visual_review':'All main and table pages rendered and reviewed in contact sheets; mechanism, results table, appendix and first/last table pages enlarged. This is layout review, not independent scientific verification.','pending':['Fang figure inventory reply and duplicate comparison','independent scientific review','runnable fixed-algorithm submission package','final editorial review and private cover data']}
(O/'validation.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(O/'review-package.zip','w',zipfile.ZIP_DEFLATED) as z:
    for name in ['anonymous-paper-v1.pdf','result-tables.pdf','README.md','validation.json','figure-manifest.json']:
        z.write(O/name,name)
    for name in ['main.tex','result-tables.tex']:z.write(O/name,'source/'+name)
    for name in ['gmcm2026.cls','gmcm-numerical.bst']:z.write(T/name,'source/'+name)
    for f in sorted((T/'fonts').iterdir()):
        if f.is_file() and not f.name.startswith(('.', '._')):z.write(f,'source/fonts/'+f.name)
    for f in figures:z.write(P/f['file'],'source/'+f['file'])
    for name in ['all-results.csv','source-receipt.json','summary.json']:
        if (P/'data'/name).exists():z.write(P/'data'/name,'data/'+name)
    for f in sorted((P/'chapters').glob('*.md')):z.write(f,'manuscript/'+f.name)
    for name in ['FIGURE_PRODUCTION_PROTOCOL.md','TERMINOLOGY.md','VALIDATION.md']:z.write(P/name,'manuscript/'+name)
print(json.dumps(receipt,ensure_ascii=False,indent=2))
print('Review ZIP:',(O/'review-package.zip').stat().st_size,'bytes')
