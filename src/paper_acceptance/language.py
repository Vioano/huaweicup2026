"""Source-bound review candidates and immutable author report imports."""
from __future__ import annotations
import hashlib
import json
import re
import subprocess
from pathlib import Path
from .core import ROOT, utc


def scan_text(text, rules, paper_sha256):
    entries = []
    for page, content in enumerate(text.split('\f'), 1):
        compact = re.sub(r'\s+', ' ', content).strip()
        for index, rule in enumerate(rules):
            for match in re.finditer(rule['term'], compact):
                left = max(compact.rfind(c, 0, match.start()) for c in '。；！') + 1
                right = compact.find('。', match.end())
                right = len(compact) if right < 0 else right + 1
                left = max(left, match.start() - 95)
                right = min(right, match.end() + 140)
                while left < match.start() and compact[left].isspace():
                    left += 1
                identity = f'{paper_sha256}:{page}:{index}:{match.start()}'
                entries.append(dict(
                    id='LG-' + hashlib.sha256(identity.encode()).hexdigest()[:10],
                    page=page, term=match.group(), original=compact[left:right].rstrip(),
                    match_start=match.start()-left, match_end=match.end()-left,
                    issue=rule['issue'], requirement=rule['requirement'], kind=rule['kind'],
                    english_candidate=rule.get('english'), status='open', offset=match.start(),
                    review_item='L01' if rule['kind'] == '优先审改' else 'L02'))
    return sorted(entries, key=lambda e: (e['page'], e['offset'], e['term']))


def import_author_report(board, commit, path):
    """Read only a fixed Git object; do not execute author code or trust its status."""
    if not re.fullmatch('[0-9a-f]{40}', commit):
        raise ValueError('作者报告必须绑定完整40位提交')
    if not path.startswith('paper/') or '..' in Path(path).parts or not path.endswith('.json'):
        raise ValueError('只导入paper目录中的JSON报告')
    result = subprocess.run(['git', '-C', str(ROOT), 'show', f'{commit}:{path}'],
                            capture_output=True, check=True, timeout=30)
    if len(result.stdout) > 15_000_000:
        raise ValueError('报告超过15MB')
    report = json.loads(result.stdout)
    if report.get('schema_version') != 1 or not isinstance(report.get('entries'), list):
        raise ValueError('作者报告需要schema_version=1与entries数组')
    if report.get('paper_sha256') != board.cat['paper_sha256']:
        raise ValueError('报告基线与当前稿件哈希不同；先完成新检查点登记，不能自动承接旧验收')
    required = {'chapter', 'line', 'original', 'issue', 'replacement', 'source', 'status'}
    for entry in report['entries']:
        if not isinstance(entry, dict) or not required <= entry.keys() or not isinstance(entry['original'], str):
            raise ValueError('作者报告缺少逐处位置、原句、问题、改句、来源或状态')
    receipt = dict(commit=commit, path=path,
                   url=f"https://github.com/{board.cat['repo']}/blob/{commit}/{path}",
                   sha256=hashlib.sha256(result.stdout).hexdigest(), imported_at=utc(),
                   paper_sha256=report['paper_sha256'], author_status_only=True,
                   scope=report.get('scope'), method=report.get('method'), entries=report['entries'])
    target = board.state / 'author-reports.json'
    reports = json.loads(target.read_text()) if target.exists() else []
    if not any(r['sha256'] == receipt['sha256'] and r['commit'] == commit for r in reports):
        reports.append(receipt)
        temporary = target.with_suffix('.tmp')
        temporary.write_text(json.dumps(reports, ensure_ascii=False, indent=2)+'\n')
        temporary.replace(target)
    return {'imported': len(receipt['entries']), 'commit': commit, 'sha256': receipt['sha256'],
            'author_status_only': True, 'acceptance_changed': False}
