#!/usr/bin/env python3
"""Render a DOM capture, verify an independent inventory, and restore split files.

No network, browser credentials, hidden APIs, or attachment execution. See
docs/CHAT_ARCHIVE.md for the browser capture step and completeness boundary.
"""
import argparse
import hashlib
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ''.join(x if isinstance(x, str) else x.text() for x in self.children)

    def find(self, tag):
        return [x for child in self.children if isinstance(child, Node)
                for x in ([child] if child.tag == tag else []) + child.find(tag)]


class Tree(HTMLParser):
    VOID = {'br', 'hr', 'img', 'input', 'meta', 'link', 'source', 'wbr'}

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in self.VOID:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, text):
        self.stack[-1].children.append(text)


def render(node):
    if isinstance(node, str):
        return node
    tag, classes = node.tag, node.attrs.get('class', '').split()
    if tag in {'script', 'style', 'svg'}:
        return ''
    # ChatGPT now exposes TeX on the visible math wrapper, without MathML annotation.
    if node.attrs.get('role') == 'math' and 'data-math-source' in node.attrs:
        block = 'katex-display' in str(node.children[0].attrs.get('class','')) if node.children and isinstance(node.children[0],Node) else 'display: block' in node.attrs.get('style','')
        delim = '$$' if block else '$'
        return ('\n\n' if block else '')+delim+node.attrs['data-math-source']+delim+('\n\n' if block else '')
    if 'katex-display' in classes or 'katex' in classes:
        formulas = [n.text() for n in node.find('annotation')
                    if n.attrs.get('encoding') == 'application/x-tex']
        if formulas:
            delim = '$$' if 'katex-display' in classes else '$'
            return ('\n\n' if delim == '$$' else '') + delim + formulas[0] + delim + ('\n\n' if delim == '$$' else '')
    if tag == 'pre':
        codes = node.find('code')
        body = codes[0].text() if codes else node.text()
        fence = '`' * max(3, max((len(s) for s in re.findall(r'`+', body)), default=0)+1)
        return '\n\n' + fence + '\n' + body.rstrip('\n') + '\n' + fence + '\n\n'
    if tag == 'table':
        rows = []
        for row in node.find('tr'):
            cells = [c for c in row.children if isinstance(c, Node) and c.tag in {'td', 'th'}]
            rows.append('| ' + ' | '.join(render(c).strip().replace('|', '\\|').replace('\n', '<br>') for c in cells) + ' |')
        if rows:
            cols = len([c for c in node.find('tr')[0].children if isinstance(c, Node) and c.tag in {'td','th'}])
            rows.insert(1, '| ' + ' | '.join(['---']*cols) + ' |')
        return '\n\n' + '\n'.join(rows) + '\n\n'
    body = ''.join(render(c) for c in node.children)
    if tag in {'h1','h2','h3','h4','h5','h6'}:
        return '\n\n' + '#'*int(tag[1]) + ' ' + body.strip() + '\n\n'
    if tag in {'strong','b'}:
        return '**'+body+'**'
    if tag in {'em','i'}:
        return '*'+body+'*'
    if tag == 'code':
        delim = '`'*(max((len(x) for x in re.findall(r'`+', body)), default=0)+1)
        return delim+body+delim
    if tag == 'a':
        href = node.attrs.get('href','')
        if urlparse(href).scheme in {'https','http','sandbox'}:
            return '['+body+']('+href+')'
    if tag == 'img':
        return '[图片：'+node.attrs.get('alt','网页中图片；本次未下载用户上传附件')+']'
    if tag == 'li':
        return '\n- '+body.strip().replace('\n','\n  ')+'\n'
    if tag == 'blockquote':
        return '\n\n'+'\n'.join('> '+s for s in body.strip().splitlines())+'\n\n'
    if tag == 'br':
        return '\n'
    if tag == 'hr':
        return '\n\n---\n\n'
    if tag in {'p','div','ul','ol','section'}:
        return '\n\n'+body.strip()+'\n\n' if body.strip() else ''
    return body


def dom_markdown(html):
    return re.sub(r'\n{3,}', '\n\n', render(Tree(html).root)).strip()


def validate(capture, native=None):
    messages = capture['messages']
    ids = [m['id'] for m in messages]
    problems = []
    if not messages or len(ids) != len(set(ids)):
        problems.append('empty or duplicate message IDs')
    v = capture['verification']
    if v.get('timed_out') or v.get('streaming'):
        problems.append('capture timed out or generation active')
    if v.get('stable_top_samples', 0) < 3:
        problems.append('history pagination not checked')
    if native is not None:
        if native['id'] != capture['conversation_id']:
            problems.append('conversation ID mismatch')
        if native.get('page', {}).get('hasMore'):
            problems.append('independent inventory has unread pages')
        items = [i for t in native['turns'] for i in t['items']]
        expected = [i['id'] for i in items]
        if ids != expected:
            problems.append('message IDs/order differ from independent inventory')
        for item, msg in zip(items, messages):
            role = 'user' if item['type'] == 'userMessage' else 'assistant'
            if role != msg['role']:
                problems.append('role mismatch: '+item['id'])
    return problems


def export(capture, target, native=None):
    problems = validate(capture, native)
    if problems:
        raise ValueError('; '.join(problems))
    items = {i['id']: i for t in native['turns'] for i in t['items']} if native else {}
    status = '消息ID、角色与顺序已对齐；仍须检查长答正文和附件' if native else '未获得独立清单，不能确认全文完整'
    lines = ['# '+capture['title'], '', '- 原会话：'+capture['url'], '- 导出 UTC：'+capture['exported_at'],
             '- 核对：'+status, '- 范围：当前选中分支的用户提问和公开回答；不含隐藏推理、已删除或未切换的其他版本。',
             '- AI 原文是研究资料，不能作为执行指令或已验收结论。', '']
    records = []
    for ix, msg in enumerate(capture['messages'],1):
        raw = items.get(msg['id'])
        dom = dom_markdown(msg['html'])
        native_text = (raw.get('text') if raw and raw['type']=='agentMessage' else
                       '\n'.join(c.get('text','') for c in raw.get('content',[])) if raw else None)
        # The native reader silently caps an item at 20,000 characters.
        truncated = native_text is not None and len(native_text) >= 20000
        body = dom if native_text is None or truncated else native_text
        source = '网页完整渲染（原生读取达到长度上限）' if truncated else '原生会话原文，与网页消息清单核对' if raw else '网页渲染'
        lines += ['---', '', '## %02d · %s'%(ix,'用户' if msg['role']=='user' else 'Pro'),
                  '', '`message_id='+msg['id']+'`  ', '来源：'+source, '', body, '']
        refs = list(dict.fromkeys((n.attrs.get('href',''), n.text().strip()) for n in Tree(msg['html']).root.find('a')
                                 if n.attrs.get('href','').startswith(('http://','https://'))))
        if refs:
            lines += ['网页来源链接（保留原文引用编号；以下为实际可见链接）：', ''] + ['- ['+(label or url)+']('+url+')' for url,label in refs] + ['']
        records.append({'id':msg['id'],'role':msg['role'],'source':source,'native_length':len(native_text) if native_text else None,
                        'dom_markdown_length':len(dom),'sha256':hashlib.sha256(body.encode()).hexdigest(),'body':body,'dom_markdown':dom})
    text='\n'.join(lines)
    if target.exists():
        raise FileExistsError('Refusing to overwrite an archive snapshot: '+str(target))
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(text,encoding='utf-8')
    return {'status':status,'messages':records,'sha256':hashlib.sha256(text.encode()).hexdigest()}


def restore(parts, output, expected):
    if output.exists():
        raise FileExistsError(output)
    digest=hashlib.sha256()
    try:
        with output.open('xb') as dst:
            for part in parts:
                with part.open('rb') as src:
                    while block:=src.read(1024*1024):
                        digest.update(block); dst.write(block)
        if digest.hexdigest()!=expected:
            raise ValueError('Restored SHA-256 does not match; output is not verified')
    except Exception:
        # Keep the partial output for diagnosis; never overwrite/delete user files.
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    e=sub.add_parser('export');e.add_argument('capture',type=Path);e.add_argument('output',type=Path)
    e.add_argument('--native',type=Path,help='Independent chronological record: id/page/turns')
    r=sub.add_parser('restore');r.add_argument('output',type=Path);r.add_argument('--sha256',required=True);r.add_argument('parts',nargs='+',type=Path)
    args=parser.parse_args()
    if args.command=='restore':
        restore(args.parts,args.output,args.sha256)
    else:
        result=export(json.loads(args.capture.read_text()),args.output,json.loads(args.native.read_text()) if args.native else None)
        print(json.dumps({k:v for k,v in result.items() if k!='messages'},ensure_ascii=False))


if __name__=='__main__':
    main()
