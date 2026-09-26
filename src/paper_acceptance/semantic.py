"""Validate bounded worker annotations without changing acceptance state."""
from __future__ import annotations
import re


def validate_workflow(data):
    if data.get('schema_version') != 2:
        raise ValueError('批注数据版本须为2')
    events, classes = data['events'], data['issue_classes']
    ids, keys, class_ids = set(), set(), set()
    for e in events:
        if not re.fullmatch(r'[0-9a-f]{40}', e['source_commit']) or not re.fullmatch(r'[0-9a-f]{64}', e['paper_sha256']):
            raise ValueError('批注缺少固定原稿身份')
        if e['annotation_id'] in ids or e['event_key'] in keys:
            raise ValueError('批注事件重复')
        if e['event_key'] != e['paper_sha256'] + ':' + e['annotation_id']:
            raise ValueError('批注去重键与源稿身份不符')
        if not e['original'] or not e.get('user_comment_verbatim', e.get('user_comment_summary')):
            raise ValueError('批注原文或用户意见缺失')
        if e['page'] < 1 or len(e['rect']) != 4 or any(not isinstance(n, (int,float)) for n in e['rect']):
            raise ValueError('批注页码或矩形不合法')
        ids.add(e['annotation_id']); keys.add(e['event_key'])
    for c in classes:
        if c['id'] in class_ids or not c['annotation_ids'] or not set(c['annotation_ids']).issubset(ids):
            raise ValueError('类别重复或无法回指人工实例')
        for field in ('title','mechanism','scope','positive_example','negative_example','rules','coverage_status'):
            if not c.get(field):
                raise ValueError('类别缺少判别依据或覆盖说明')
        class_ids.add(c['id'])
    return {'valid': True, 'events': len(events), 'issue_classes': len(classes), 'acceptance_changed': False}


def combine_reports(inputs, reports):
    if len(inputs) != len(reports) or not inputs:
        raise ValueError('每个分章输入必须有一份报告')
    source = inputs[0]['source_commit']
    standard = inputs[0]['standard_version']
    coverage, findings, workers = [], [], []
    seen_units, seen_findings = set(), set()
    for packet, report in zip(inputs, reports):
        if any(d['source_commit'] != source or d['standard_version'] != standard for d in (packet, report)):
            raise ValueError('新旧稿或标准版本不一致')
        units = {u['id']: u for u in packet['entries']}
        rows = report['coverage']
        ids = [r['unit_id'] for r in rows]
        if len(units) != len(packet['entries']) or len(ids) != len(set(ids)) or set(ids) != set(units):
            raise ValueError('覆盖清单缺失、重复或包含未知单元')
        if seen_units.intersection(units):
            raise ValueError('分章范围重叠')
        seen_units.update(units)
        for row in rows:
            if row['assessment'] not in {'findings', 'reviewed_no_finding', 'needs_context'}:
                raise ValueError('初审结果不能作为最终通过状态')
            unit = units[row['unit_id']]
            coverage.append({**row, 'path': unit['path'], 'line': unit['line'], 'worker': report['worker']})
        for finding in report['findings']:
            unit = units.get(finding['unit_id'])
            if not unit or finding['path'] != unit['path'] or finding['line'] < unit['line'] or finding['line'] > unit['line_end']:
                raise ValueError('标注位置与固定输入不符')
            if not finding['original'] or finding['original'] not in unit['original']:
                raise ValueError('引文不是固定新稿的连续原文')
            if finding['id'] in seen_findings:
                raise ValueError('问题ID重复')
            if not finding['rules'] or not set(finding['rules']).issubset({f'L{i:02d}' for i in range(1, 14)}):
                raise ValueError('未知语言验收项')
            seen_findings.add(finding['id'])
            findings.append({**finding, 'worker': report['worker'], 'source_commit': source,
                             'supervisor_status': 'pending', 'supervisor_note': '', 'author_status': 'not_delivered',
                             'source_url': f"https://github.com/huaweibei123/huaweicup2026/blob/{source}/{finding['path']}#L{finding['line']}"})
        workers.append({k: report.get(k) for k in ('worker', 'model', 'reasoning', 'scope', 'limitations', 'budget')})
    return {'schema_version': 1, 'source_commit': source, 'standard_version': standard,
            'state': 'worker_reports_received', 'workers': workers, 'coverage': coverage, 'findings': findings,
            'scope': '11章源文的段落、标题、表格和公式块；未检查新PDF和图内文字，不代表最终验收通过。'}
