"""Export nine existing Stage B units. Only git reads; no solver/evaluator imports."""
from pathlib import Path
from functools import lru_cache
import gzip
import hashlib
import io
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SOURCE = '0b58c123cccf02fc993b741d79dcd8511e4dd38f'
BASE = 'results/a/q2-yuanzhifang/stage-b-20260924-042906/'
SESSION = 'yuanzhifang30-sudo/s-c909b5a9a43b4bc78807afcf27341a38'
REPO = 'huaweibei123/huaweicup2026'
ISSUE = f'https://github.com/{REPO}/issues/33'


def sha(data):
    return hashlib.sha256(data).hexdigest()


@lru_cache(maxsize=None)
def git(path, commit=SOURCE):
    return subprocess.check_output(['git', 'show', f'{commit}:{path}'], cwd=ROOT)


def save(path, raw):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() != raw:
        raise ValueError(f'Refusing to overwrite changed snapshot: {path.name}')
    path.write_bytes(raw)
    return {'path': path.relative_to(ROOT).as_posix(), 'sha256': sha(raw)}


def dump(path, obj):
    return save(path, (json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def code(commit, path, entrypoint):
    git(path, commit)  # Every linked code source must actually resolve.
    return {'repo': REPO, 'commit': commit, 'path': path, 'entrypoint': entrypoint}


def null_reasons(obj, prefix='provenance'):
    found = {}
    for key, val in obj.items():
        field = f'{prefix}.{key}'
        if key in ('missing_reasons', 'failure', 'selected_algorithm_id', 'selected_solver_commit'):
            continue
        if isinstance(val, dict):
            found.update(null_reasons(val, field))
        elif val is None:
            found[field] = '原历史收据未记录此项；本次仅导出，未重跑或用当前机器状态补造。'
    return found


def main():
    archives = json.loads(git(BASE + 'evidence_manifest.json'))
    summary = json.loads(git(BASE + 'summary.json'))
    official = json.loads(git('docs/a/source-manifest.json'))
    frozen = {r['path']: r['sha256'] for r in official['files']}
    provenance_rows, records = [], []
    full_members = 0
    definitions = {
        'D': ('q2-contiguous-baseline', '拓扑连续块基线', '拓扑连续块构造，初评后原计划最终确认。'),
        'M1': ('q2-packet-core-search', '包结构分核有界搜索', '从D出发比较包结构/核心分配候选，以官方E0选优；含退化候选和D回退。'),
        'M2': ('q2-fixed-core-priority-search', '固定核心归属优先级搜索', '固定D的核心归属，比较核内拓扑优先级和粒度，以官方E0选优；含D回退。'),
    }
    for unit in summary['units']:
        name = unit['case'] + '-' + unit['method']
        meta = archives[name]
        raw_zip = git(BASE + meta['archive'])
        assert len(raw_zip) == meta['bytes'] and sha(raw_zip) == meta['sha256']
        with zipfile.ZipFile(io.BytesIO(raw_zip)) as z:
            expected_names = {name + '/' + member for member in meta['members']}
            assert set(z.namelist()) == expected_names
            for member, expected in meta['members'].items():
                raw = z.read(name + '/' + member)
                assert len(raw) == expected['bytes'] and sha(raw) == expected['sha256']
                full_members += 1

            def read(member):
                return z.read(name + '/' + member)

            run = json.loads(read('summary.json'))
            controller = json.loads(read('controller.json'))
            final = run['final']
            assert run['status'] == 'confirmed' and run['full_repeat_equal']
            assert final['status'] == 'ok' and final['returncode'] == 0
            assert controller['status'] == 'completed' and controller['returncode'] == 0
            assert run['head'] == unit['evaluated_head']
            assert run['calls_charged'] == unit['calls'] == len(run['results'])
            assert all(c['status'] == 'ok' and c['launched'] for c in run['results'])
            assert run['graph_sha256'] == frozen[f'data/case_{unit["case"]}.json']
            assert run['config_sha256'] == frozen['data/config.txt']
            for path, digest in run['source_hashes'].items():
                assert sha(git(path, run['head'])) == digest
            # Check the actual code/config at each as-run commit against the frozen bytes.
            for spec in official['files']:
                if spec['path'].startswith('code/') or spec['path'] == 'data/config.txt':
                    assert sha(git('data/raw/a/official/' + spec['path'], run['head'])) == spec['sha256']
            plan_member = final['plan'].removeprefix(BASE + name + '/')
            result_member = final['output'].removeprefix(BASE + name + '/') + '/result.json'
            plan_bytes, result_bytes = read(plan_member), read(result_member)
            result = json.loads(result_bytes)
            assert sha(plan_bytes) == final['plan_sha256']
            assert set(json.loads(plan_bytes)) == {'node_to_subgraph', 'core_schedules'}
            assert result['makespan'] == final['makespan'] == unit['best_cycles']
            assert result['scene'] == 'B' and result['num_cores'] == 4
            assert result['data_movement_bytes'] == final['movement']
            incumbent_result = run['incumbent']['output'].removeprefix(BASE + name + '/') + '/result.json'
            assert json.loads(read(incumbent_result)) == result
            exports = {}
            for label, member, filename in [
                ('plan', plan_member, 'plan.json'),
                ('result', result_member, 'result.json.gz'),
                ('run', 'summary.json', 'run.json'),
                ('controller', 'controller.json', 'controller.json'),
                ('calls', 'calls.json', 'calls.json'),
            ]:
                original = read(member)
                stored = gzip.compress(original, mtime=0) if filename.endswith('.gz') else original
                if filename.endswith('.gz'):
                    assert gzip.decompress(stored) == original
                artifact = save(OUT / name / filename, stored)
                exports[label] = artifact
                provenance_rows.append({
                    'unit': name, 'source_commit': SOURCE, 'archive_path': BASE + meta['archive'],
                    'archive_sha256': meta['sha256'], 'member': name + '/' + member,
                    'original_bytes': len(original), 'original_sha256': sha(original),
                    'stored_bytes': len(stored), 'stored': artifact,
                    'transformation': 'gzip, lossless, mtime=0' if filename.endswith('.gz') else 'byte-for-byte copy',
                })

        algorithm, title, method = definitions[unit['method']]
        source = code(run['head'], 'src/q2/budget_search.py', 'python -X utf8 -B -m src.q2.budget_search')
        p = {
            'producer_session': SESSION, 'task_url': ISSUE,
            'solver': {
                'source': source, 'authors': ['yuanzhifang30-sudo'], 'method': method,
                'references': [f'https://github.com/{REPO}/blob/{SOURCE}/{BASE}REPORT.md'],
                'upstream': [code(run['head'], 'src/q2/construct.py', 'python -m src.q2.construct')],
                'selected_algorithm_id': None, 'selected_solver_commit': None,
            },
            'runner': {
                'source': code(run['head'], 'src/q2/stage_b.py', 'python -X utf8 -B -m src.q2.stage_b'),
                'argv': controller['command'], 'working_directory': '.',
            },
            'environment': {
                'os': run['platform'], 'cpu': None, 'gpu': None, 'ram_bytes': None,
                'python': run['python'], 'dependencies': 'uv.lock SHA256=' + run['uv_lock_sha256'],
                'threads': None, 'workers': 1, 'peak_rss_bytes': None,
            },
            'measurement': {
                'started_at': None, 'finished_at': None, 'seed': unit['seed'], 'repeat_index': 0,
                'cold_start': None,
                'solver_scope': '历史controller unit从worker启动前至清理/收据；包含读图、构造、全部在线E0和最终确认。参数保留unit wall；缺少可独立复用通用solver的完整外层墙钟，标准solver_wall留null。',
                'evaluation_scope': '全部E0在历史搜索unit内部；没有独立外部最终复评时间。参数保留最后一次内部确认wall，不能与unit wall相加。',
                'budget': {'wall_seconds': 600, 'candidate_limit': None, 'stop_reason': run['early_stop']},
                'calls': {'solver': 1, 'E0': unit['calls'], 'E1': 0, 'E2': 0},
                'offline_costs': None, 'failure': None,
            },
            'missing_reasons': {},
        }
        p['missing_reasons'] = null_reasons(p)
        p['missing_reasons']['provenance.environment.peak_rss_bytes'] = '只保存250ms采样的Windows controller/job working-set峰值，非严格peak RSS，保留在parameters。'
        p['missing_reasons']['provenance.measurement.budget.candidate_limit'] = '原限制为每unit最多32次E0，不等于候选数量；有限候选清单及去重保留在run原件。'
        p['missing_reasons']['provenance.measurement.offline_costs'] = '原实验记录预装环境/固定原件；未计离线安装成本。测后打包/报告成本另见原REPORT，不并入solver wall。'
        movement = result['data_movement_bytes']
        records.append({
            'attempt_id': f'fang-stage-b-20260924-{name}-p2-k4-seed0', 'revision': 1,
            'run_id': f'fang-stage-b-20260924-{unit["method"].lower()}-{run["head"][:12]}',
            'algorithm_id': algorithm, 'algorithm_name': title, 'variant': 'stage-b-' + unit['method'].lower() + '-e0-confirmed',
            'solver_commit': run['head'],
            'parameters': {
                'method': unit['method'], 'seed': 0, 'cores': 4, 'workers': 1,
                'max_e0_calls_per_unit': 32, 'max_wall_seconds_per_unit': 600,
                'max_e0_calls_stage': 288, 'max_wall_seconds_stage': 5400,
                'normal_call_timeout_seconds': 120, 'final_call_timeout_seconds': 105,
                'sampled_memory_stop_bytes': 4294967296, 'sample_interval_seconds': 0.25,
                'stop_policy': 'historical fixed implementation; see as-run commit and original REPORT',
                'best_specification': unit['best_specification'],
                'observed_unit_wall_seconds': unit['unit_seconds'],
                'controller_receipt_unit_wall_seconds': unit['controller_receipt_unit_seconds'],
                'all_online_e0_wall_seconds': unit['evaluation_seconds'],
                'final_internal_confirmation_wall_seconds': final['wall_seconds'],
                'sampled_peak_working_set_bytes': unit['peak_working_set_bytes'],
                'duplicates': unit['duplicates'], 'worse_than_initial': unit['worse_than_initial'],
                'stage_active_unit_seconds': summary['active_unit_seconds'],
                'stage_envelope_seconds': summary['stage_envelope_seconds'],
            },
            'problem': 'P2', 'case_id': unit['case'], 'cores': 4, 'status': 'ok',
            'metrics': {
                'makespan_cycles': result['makespan'], 'solver_wall_seconds': None,
                'evaluation_wall_seconds': None, 'ddr_bytes': movement['scheduled_copy_bytes'],
                'extra_ddr_bytes': movement['added_copy_bytes'], 'spill_bytes': movement['spill_added_copy_bytes'],
                'cache_hit_rate': None,
            },
            'evaluator': {'route': 'E0', 'commit': run['head'], 'entrypoint': 'data/raw/a/official/code/multicore_cut_evaluate_problem_2.py'},
            'identity': {'graph_sha256': run['graph_sha256'], 'config_sha256': run['config_sha256'],
                         'official_sha256': official['official_code_hash'], 'plan_sha256': sha(plan_bytes)},
            'artifacts': {k: exports[k] for k in ('plan', 'result', 'run')},
            'runtime_id': 'fang-stage-b-windows11-python31214', 'observed_at': None,
            'timing': {'solver_includes_evaluation': None, 'evaluation_precision': None,
                       'utc': '原stage T0=2026-09-23T20:44:57.229279Z；unit仅记录monotonic，不推算绝对UTC。'},
            'provenance': p,
            'notes': [
                '仅导出已有九个方法unit的最终确认；122次历史E0全部保留在上游九份ZIP和本包calls/run，不伪称本次新运行。',
                '九条记录覆盖三个P2/4核表格位；不是九个新用例或完整100图成绩。',
                '两个真实as-run提交分开；结果导出SHA不冒充solver版本。',
                '标准solver/evaluation wall为null；历史unit、内部E0计时和包含关系见parameters及measurement，不据此跨机器比较通用求解速度。',
                '无逐unit原始UTC/CPU/冷启动记录；没有官方单核baseline引用，速度比待匹配原件。',
                'controller.json与calls.json的字节来源在export-manifest.json；完整trace/退化/控制中断保留于固定上游ZIP和REPORT。',
                '本次校验原件和身份，未独立重跑、未代签算法最终验收。',
            ],
            'source_url': f'https://github.com/{REPO}/blob/{SOURCE}/{BASE}REPORT.md',
            'baseline': None, 'cache_pair': None,
        })
    assert len(records) == 9 and sum(r['provenance']['measurement']['calls']['E0'] for r in records) == 122
    manifest = dump(OUT / 'export-manifest.json', {
        'source_commit': SOURCE, 'verified_archives': len(archives), 'verified_archive_members': full_members,
        'new_solver_or_evaluator_calls': 0, 'scope': 'byte/hash/source consistency only; no rerun', 'exports': provenance_rows,
    })
    for record in records:
        record['artifacts']['manifest'] = manifest
    dump(OUT / 'board-feed-stage-b-20260924.json', {'schema_version': 1, 'submission_version': 1, 'records': records})
    print(json.dumps({'records': len(records), 'cells': 3, 'verified_members': full_members, 'new_calls': 0}))


if __name__ == '__main__':
    main()
