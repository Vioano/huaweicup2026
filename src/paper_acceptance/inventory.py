"""Enumerate fixed manuscript text without pretending enumeration is review."""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path
from .core import ROOT


def git_bytes(commit, path):
    return subprocess.check_output(['git','-C',str(ROOT),'show',f'{commit}:{path}'])


def build_inventory(catalogue):
    commit=catalogue['paper_commit']; units=[]; sources=[]
    paths=subprocess.check_output(['git','-C',str(ROOT),'ls-tree','-r','--name-only',commit,
                                   'paper/manuscript-v1/chapters']).decode().splitlines()
    examples=json.loads((ROOT/'docs/paper-acceptance/sentence-audit.json').read_text())['entries']
    def norm(s): return re.sub(r'[^\w\u4e00-\u9fff]','',s)
    def add(path,line,text,kind,chapter,section,scope='manuscript',page=None):
        if not text.strip(): return
        key=f'{commit}:{path}:{line}:{kind}:{text}'
        normal=norm(text)
        related=[e['id'] for e in examples if len(normal)>12 and normal in norm(e['original'])]
        units.append(dict(id='TX-'+hashlib.sha256(key.encode()).hexdigest()[:12],
                          chapter=chapter,section=section,source_path=path,line=line,original=text,
                          kind=kind,scope=scope,page=page,status='unreviewed',related_examples=related,
                          source_url=f"https://github.com/{catalogue['repo']}/blob/{commit}/{path}#L{line}"))
    for path in paths:
        if not path.endswith('.md'): continue
        raw=git_bytes(commit,path); sources.append(dict(path=path,sha256=hashlib.sha256(raw).hexdigest()))
        lines=raw.decode().splitlines();chapter=Path(path).stem;section='';plan=False;fence=False;math=False
        for line_no,line in enumerate(lines,1):
            value=line.strip()
            if not value: continue
            if value.startswith(':::'):
                plan=not plan;continue
            if value.startswith('```'):
                fence=not fence;continue
            if value.startswith('$$') or value in ('\\[','\\]'):
                math=not math
                add(path,line_no,value,'公式',chapter,section,'figure-spec' if plan else 'manuscript');continue
            scope='figure-spec' if plan else 'manuscript'
            if value.startswith('#'):
                section=value.lstrip('# ').strip()
                if value.startswith('# '): chapter=Path(path).stem+' · '+section
                add(path,line_no,section,'标题',chapter,section,scope);continue
            if re.fullmatch(r'[|:\-\s]+',value): continue
            kind='图稿说明' if plan else ('关键词' if value.startswith('**关键词') else ('参考文献' if Path(path).name.startswith('09-') else ('公式' if math else ('算法步骤' if fence else ('表格行' if value.startswith('|') else '句子')))))
            # Only sentence-ending Chinese punctuation splits prose. Tables,
            # formula blocks and algorithm lines stay intact with their source.
            parts=re.findall(r'.+?[。！？](?:[”’」』])?|.+$',value) if kind=='句子' else [value]
            for part in parts: add(path,line_no,part,kind,chapter,section,scope)
    tex_path='paper/manuscript-v1/checkpoints/checkpoint-01/main.tex'
    tex_raw=git_bytes(commit,tex_path);tex=tex_raw.decode();sources.append(dict(path=tex_path,sha256=hashlib.sha256(tex_raw).hexdigest()))
    title=re.search(r'\\gmcmsetup\{title=\{([^}]+)',tex)
    if title:add(tex_path,tex[:title.start()].count('\n')+1,title[1],'论文题目','00-title · 论文题目','论文题目',page=1)
    manifest_path='paper/manuscript-v1/checkpoints/checkpoint-01/figure-manifest.json'
    raw=git_bytes(commit,manifest_path);sources.append(dict(path=manifest_path,sha256=hashlib.sha256(raw).hexdigest()))
    figures=json.loads(raw)
    page_by_file={i['figure']['file'].removeprefix('paper/manuscript-v1/'):i['page'] for i in catalogue['items'] if i.get('figure')}
    for index,figure in enumerate(figures,1):
        # Use the checkpoint's actual caption, rather than draft figure-plan prose.
        caption=figure['caption']; found=tex.find('\\caption{'+caption+'}')
        line=tex[:found].count('\n')+1 if found>=0 else 1
        add(tex_path,line,caption.replace('\\_','_'),'图注',f'11-captions · 实际图注','图'+str(index),page=page_by_file.get(figure['file']))
        add('paper/manuscript-v1/'+figure['file'],1,'该幅图内的全部文字仍须逐项人工转录、解释并回读。','图内文字待检查',f'12-artwork · 图内文字','图'+str(index),scope='image-review-pending',page=page_by_file.get(figure['file']))
    units.sort(key=lambda e:(e['chapter'],e['source_path'],e['line']))
    return dict(schema_version=1,paper_commit=commit,paper_sha256=catalogue['paper_sha256'],
                scope='固定源稿逐句枚举；正文、标题、表格、公式、算法、实际图注及图内文字检查任务分别标明。图稿说明不计入正文句子。未审状态不自动判错，也不自动通过；现有实例关联只帮助定位，不代替逐句审阅。',
                sources=sources,entries=units)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True);a=p.parse_args()
    cat=json.loads((ROOT/'docs/paper-acceptance/catalogue.json').read_text());result=build_inventory(cat)
    Path(a.output).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'units':len(result['entries']),'reviewed':0,'accepted':0},ensure_ascii=False))

if __name__=='__main__':main()
