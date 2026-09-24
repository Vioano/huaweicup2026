"""Adapt the fixed, pre-protocol LYX snapshot without running submitted code.

Only terminal solver receipts become attempts. Shared baseline anchors and
unconfirmed/missing positions remain in coverage, not invented solver runs.
All multi-core results remain reported because their original bytes are absent.
"""
from __future__ import annotations
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = 'e041bca2dcf825a55353765303b218491f351e2d'
SNAPSHOT = 'results/a/p123-multicore-20260924/snapshots/20260924T121711.278791Z/'
DEST = 'results/benchmark-board/lyx-snapshot-20260924T121711/'
BASELINES = 'results/benchmark-board/official-singlecore-20260924'
URL = 'https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5814158425'
ALGORITHMS = {'P1': ('q1-bounded-search', '有预算结构候选搜索', 'src/q1/search.py', 'search'),
              'P2': ('q2-contiguous-baseline', '拓扑连续块基线', 'src/q2/construct.py', 'main'),
              'P3': ('q3-structure-selected', '结构守卫选择构造', 'src/q3/solve.py', 'main')}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return subprocess.check_output(['git', 'show', SOURCE + ':' + path], cwd=ROOT)


def output(path, obj):
    target = ROOT / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def number(text):
    return json.loads(text) if text else None


def baseline(case, identity):
    path = ROOT / BASELINES / case / 'run.json'
    if not path.exists():
        return None
    receipt = json.loads(path.read_text())
    if receipt['status'] != 'ok':
        return None
    if any(receipt[k] != identity[v] for k, v in (
            ('graph_sha256', 'graph_sha256'), ('config_sha256', 'config_sha256'),
            ('official_code_hash', 'official_sha256'))):
        raise ValueError('baseline identity mismatch')
    ref = receipt['artifacts']['result.json']
    return dict(graph_sha256=identity['graph_sha256'], config_sha256=identity['config_sha256'],
                official_sha256=identity['official_sha256'], route='E0',
                entrypoint='singlecore_evaluate.evaluate_singlecore',
                result={k:ref[k] for k in ('path', 'sha256')})


def main():
    raw = read(SNAPSHOT + 'manifest.json')
    if digest(raw) != '67a8315320d4b6ca68b3dd7344be18e8766e83ce4530941e589dce32a8e9b97d':
        raise ValueError('snapshot manifest mismatch')
    manifest = json.loads(raw)
    files = {'manifest.json': raw}
    for name, item in manifest['files'].items():
        value = read(SNAPSHOT + name)
        if digest(value) != item['sha256'] or len(value) != item['bytes']:
            raise ValueError('snapshot bytes mismatch: ' + name)
        files[name] = value
    for name, value in files.items():
        path = ROOT / DEST / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    rows = list(csv.DictReader(io.StringIO(files['comparison.csv'].decode('utf-8-sig'))))
    if len(rows) != 1500 or len({(r['problem'], r['case'], r['cores']) for r in rows}) != 1500:
        raise ValueError('snapshot position coverage mismatch')
    receipts = {r['source']: r for r in map(json.loads, files['receipts.jsonl'].splitlines())}
    protocol = json.loads(files['protocol.json'])
    frozen_raw = (ROOT / 'docs/a/source-manifest.json').read_bytes()
    # The member's Windows checkout captured this JSON with CRLF. Verify that
    # exact byte variant, not a permissive semantic-only hash comparison.
    manifest_variant = 'LF' if digest(frozen_raw)==protocol['official_source_manifest_sha256'] else 'CRLF'
    declared_raw = frozen_raw if manifest_variant=='LF' else frozen_raw.replace(b'\n',b'\r\n')
    if digest(declared_raw) != protocol['official_source_manifest_sha256']:
        raise ValueError('declared frozen manifest differs')
    frozen = json.loads(frozen_raw)
    expected = {r['path']: r['sha256'] for r in frozen['files']}
    old = json.loads((ROOT / 'results/benchmark-board/feeds/board-feed-initial-20260924.json').read_text())
    old = {(r['problem'], r['case_id'], r['cores']): r for r in old['records'][2:]}
    template = json.loads((ROOT / 'docs/benchmarks/examples/submission-v1.json').read_text())['records'][0]
    adapted = []
    for row in rows:
        if row['slot_kind'] != 'solver' or row['capture_state'] != 'final_receipt':
            continue
        receipt = receipts[row['source_receipt']]
        if receipt['sha256'] != row['source_receipt_sha256']:
            raise ValueError('receipt reference mismatch')
        cell = receipt['extracted']; original = cell['row']
        p, case, cores = row['problem'], row['case'], int(row['cores'])
        for name in ('makespan_cycles', 'solver_wall_seconds', 'e0_wall_seconds'):
            value = number(row[name])
            if type(value) is not type(original[name]) or value != original[name]:
                raise ValueError('CSV/receipt numeric value or type mismatch: ' + name)
        if original['source_commit'] != protocol['versions'][p]['commit']:
            raise ValueError('unexpected solver identity')
        r = copy.deepcopy(template)
        known = old.get((p, case, cores))
        r.update(attempt_id=known['attempt_id'] if known else f'lyx-p123-20260924-{p}-{case}-k{cores}',
                 revision=2 if known else 1,
                 run_id=known['run_id'] if known else 'lyx-p123-multicore-20260924',
                 problem=p, case_id=case, cores=cores, status='ok' if row['status']=='ok' else 'failed',
                 algorithm_id=ALGORITHMS[p][0], algorithm_name=ALGORITHMS[p][1],
                 solver_commit=original['source_commit'],
                 variant='search-e1-e0-confirm' if p=='P1' else 'contiguous' if p=='P2' else cell.get('p3_strategy','unknown'),
                 runtime_id='lyx-windows-20260924-2workers',
                 observed_at=cell['finished_at'].replace('+00:00','Z'), source_url=URL)
        r['parameters'] = cell.get('p1_search',{}).get('parameters',{}) if p=='P1' else {'cores':cores}
        r['identity'] = dict(graph_sha256=expected[f'data/case_{case}.json'],
                             config_sha256=expected['data/config.txt'],
                             official_sha256=frozen['official_code_hash'], plan_sha256=row['plan_sha256'] or None)
        r['metrics'].update(makespan_cycles=original['makespan_cycles'], solver_wall_seconds=original['solver_wall_seconds'],
                            evaluation_wall_seconds=original['e0_wall_seconds'] if p=='P2' else None,
                            cache_hit_rate=original['cache_hit_rate'])
        movement = json.loads(original['data_movement_bytes']) if original['data_movement_bytes'] else {}
        for metric,key in [('ddr_bytes','scheduled_copy_bytes'),('extra_ddr_bytes','added_copy_bytes'),('spill_bytes','spill_added_copy_bytes')]:
            r['metrics'][metric] = movement.get(key)
        # This is a source declaration: original final result/plan bytes are absent.
        r['evaluator'] = dict(route='E0', commit=None,
                             entrypoint={'P1':'multicore_cut_evaluate_problem_1.evaluate_scene_a',
                                         'P2':'multicore_cut_evaluate_problem_2.evaluate_scene_b',
                                         'P3':'multicore_cut_evaluate_problem_3.evaluate_problem_3'}[p])
        r['artifacts'] = {}
        r['baseline'] = baseline(case, r['identity'])
        r['cache_pair'] = None
        r['reported_baseline_cycles'] = original['singlecore_cycles']
        r['reported_cache_ratio'] = original['cache_speedup']
        r['timing'].update(solver_includes_evaluation=p!='P2', utc='UTC',
                           source_e0_component_seconds=original['e0_wall_seconds'],
                           source_cell_wall_seconds=cell.get('cell_wall_seconds'),
                           source_pair_wall_seconds=number(row['pair_wall_seconds']))
        r['reported_source'] = dict(commit=SOURCE, path=SNAPSHOT, receipt_path=row['source_receipt'],
                                    receipt_sha256=row['source_receipt_sha256'],
                                    harness_sha256=row['harness_sha256'], lineage=row['harness_lineage_basis'],
                                    identity_basis='snapshot protocol pins frozen manifest; original multi-core files absent')
        prov=r['provenance']
        prov['producer_session']='lyx0217/s-89ad75751f054b6b9929e42d899246be'
        prov['solver'].update(source=dict(repo='huaweibei123/huaweicup2026',commit=r['solver_commit'],
                                         path=ALGORITHMS[p][2],entrypoint=ALGORITHMS[p][3]),
                              method=r['algorithm_name'], references=[URL])
        prov['runner'] = dict(source=None, argv=[], working_directory=None)
        prov['environment'].update(os=protocol['platform'],python=protocol['python'],
                                    dependencies='uv.lock SHA256 '+protocol['uv_lock_sha256'],workers=protocol['workers'])
        measure=prov['measurement']
        measure.update(started_at=cell['started_at'].replace('+00:00','Z'), finished_at=r['observed_at'],
                       seed=0 if p=='P1' else None, repeat_index=0,
                       solver_scope=row['timing_note'] or None, evaluation_scope='P2: external official process; P1/P3: included component, stored separately')
        if r['status']!='ok':
            measure['failure']=dict(stage='original_controller',reason=original['error'] or row['status_reason'],
                                    exit_code=None,elapsed_seconds=original['solver_wall_seconds'])
        prov['missing_reasons']={}
        def explain(value, prefix='provenance'):
            for key, item in value.items():
                if key=='missing_reasons':continue
                path=prefix+'.'+key
                if item is None and key not in ('failure','selected_algorithm_id','selected_solver_commit'):
                    prov['missing_reasons'][path]='固定旧快照未完整记录；不从接收时间、后改代码或提案数推造'
                elif isinstance(item,dict):explain(item,path)
        explain(prov)
        r['notes']=['固定12:17 UTC非原子快照；不是直播进度。',
                    '原plan/result/run完整原件多数仅在成员本地；本条只有轻量摘录，不入正式榜。',
                    '维护者适配首次旧格式交付；队友未运行board-submission-v1预检，维护者校验不代签其采用。',
                    'E0代码身份来自冻结协议声明，执行commit未完整记录；原始argv、硬件和总调用数不猜测。',
                    row['timing_note'] or '旧收据未逐格记录计时边界。']
        adapted.append(r)
    if len(adapted)!=749 or sum(r['status']=='ok' for r in adapted)!=697:
        raise ValueError('terminal coverage mismatch')
    from protocol import validate_feed
    feed=dict(schema_version=1,submission_version=1,records=adapted)
    validate_feed(feed,submission=True)
    output('results/benchmark-board/feeds/board-feed-lyx-partial-20260924T121711.json',feed)
    output(DEST+'adapter-receipt.json',dict(source_commit=SOURCE,source_url=URL,source_manifest_sha256=digest(raw),
           verified_snapshot_files=len(files),frozen_manifest_line_endings=manifest_variant,
           coverage=manifest['coverage'],imported_terminal_attempts=len(adapted),
           baseline_attached=sum(r['baseline'] is not None for r in adapted),
           excluded={'reused_baseline_anchors':200,'not_observed':549,'running_unconfirmed':2},
           scope='snapshot bytes and declarations only; no submitted code execution; no original multi-core artifact verification'))
    print(json.dumps({'records':len(adapted),'successful_reported':697,'failed':52,'baseline_attached':sum(r['baseline'] is not None for r in adapted)}))


if __name__=='__main__':main()
