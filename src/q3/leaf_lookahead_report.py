"""Read-only reconstruction of the four frozen one-leaf comparisons."""
import argparse
from pathlib import Path

from .band_mechanism_report import owners
from .construct import ROOT, Index, derive_multicore_plan
from .feedback_benchmark import digest, git_bytes, read, write
from .leaf_lookahead_probe import FOREST_COMMIT, BAND_COMMIT, BAND_RUN

AREA = 'results/a/q3-nikolastarx/leaf-lookahead-probe-20260925'


def projections(index, plan):
    view = derive_multicore_plan(index.graph, plan)
    op = {sg: nodes[0] for sg, nodes in view['nodes_by_subgraph'].items()}
    assert all(len(nodes) == 1 for nodes in view['nodes_by_subgraph'].values())
    return {(c, pipe): [op[sg] for sg in view['core_orders'].get(c, [])
                        if index.ops[op[sg]]['pipe'] == pipe]
            for c in range(view['num_cores']) for pipe in ('PIPE_M', 'PIPE_V')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forest-root', required=True, type=Path)
    args = parser.parse_args()
    run = read(ROOT / AREA / 'run.json')
    assert run['status'] == 'complete' and (run['new_p3'], run['new_p2']) == (4, 3)
    for path, sha in run['source_input_sha256'].items():
        assert digest(ROOT / path) == sha, path
    assert (ROOT / BAND_RUN).read_bytes() == git_bytes(ROOT, BAND_COMMIT, BAND_RUN)
    band = read(ROOT / BAND_RUN)
    coverage = read(ROOT / 'results/a/q3-nikolastarx/reuse-coverage-20260925/coordinates.json')
    rows = []
    for item in run['plans']:
        case, variant = item['case_id'], item['variant']
        if variant == 'forest':
            ref = next(r for r in coverage if r['case'] == int(case) and r['cores'] == 5)
            receipt_path = Path(ref['receipt_path'])
            assert (args.forest_root / receipt_path).read_bytes() == git_bytes(
                args.forest_root, FOREST_COMMIT, str(receipt_path))
            old_plan = args.forest_root / receipt_path.parent.parent / f'case_{case}_multicore_res.json'
            old_result = args.forest_root / receipt_path.parent / 'result.json.gz'
        else:
            p = next(r for r in band['plans'] if r['case_id'] == case and r['order_mode'] == 'pair_cache_model')
            r = next(r for r in band['results'] if r['case_id'] == case and r['order_mode'] == 'pair_cache_model' and r['problem'] == 3)
            old_plan, old_result = ROOT / p['plan_path'], ROOT / r['result_path']
        assert digest(old_plan) == item['baseline_plan_sha256']
        assert digest(old_result) == item['baseline_result_sha256']
        assert digest(ROOT / item['plan_path']) == item['plan_sha256']
        index = Index(read(ROOT / f'data/raw/a/official/data/case_{case}.json'))
        a, b = read(old_plan), read(ROOT / item['plan_path'])
        assert owners(a) == owners(b) and projections(index, a) == projections(index, b)
        old = read(old_result)
        evaluated = {}
        for r in run['evaluations']:
            if (r['case_id'], r['variant']) != (case, variant):
                continue
            assert r['status'] == 'ok' and r['plan_sha256'] == item['plan_sha256']
            assert digest(ROOT / r['result_path']) == r['result_sha256']
            raw = read(ROOT / r['result_path'])
            assert raw['num_cores'] == 5 and raw['makespan'] == r['makespan']
            assert raw['scene'] == 'B'
            if r['problem'] == 3:
                assert raw['problem'] == 3 and raw['cache_mode'] == 'read_only'
            else:
                assert 'cache_stats' not in raw
            evaluated[r['problem']] = raw
        new = evaluated[3]
        before, after = old['data_movement_bytes'], new['data_movement_bytes']
        extra = after['added_copy_bytes'] - before['added_copy_bytes']
        spill = after['spill_added_copy_bytes'] - before['spill_added_copy_bytes']
        assert before['partition_added_copy_bytes'] == after['partition_added_copy_bytes']
        assert extra == spill  # unchanged ownership; only reload traffic changed
        rows.append({'case_id': case, 'variant': variant, 'old_makespan': old['makespan'],
                     'new_makespan': new['makespan'], 'delta_makespan': new['makespan'] - old['makespan'],
                     'reduction_percent': 100 * (1 - new['makespan'] / old['makespan']),
                     'delta_extra_bytes': extra, 'delta_spill_bytes': spill,
                     'old_hit_rate': old['cache_stats']['hit_rate'],
                     'new_hit_rate': new['cache_stats']['hit_rate'],
                     'cache_gain': evaluated[2]['makespan'] / new['makespan'] if 2 in evaluated else None,
                     'construct_seconds': item['construct_seconds'],
                     'owner_and_pipe_projections_equal': True,
                     'delta_extra_equals_delta_spill': True})
    summary = {'source_commit': run['source_commit'], 'scope': run['scope'],
               'new_p3': 4, 'new_p2': 3, 'new_solver': 0, 'retries': 0,
               'elapsed_seconds': run['elapsed_seconds'], 'rows': rows}
    write(ROOT / AREA / 'comparison.json', summary)
    lines = ['# 单叶前瞻：真实内存依赖后的机制检验', '',
             '冻结源码 `' + run['source_commit'] + '`；两张已见图、四个固定 owner 对照。4 P3 + 3 同计划 P2，共 7 次未修改 E0、0 solver、0 retry、1 worker；整批 %.6f 秒。' % run['elapsed_seconds'], '',
             '| 图/原方案 | 原 M | 新 M | M 改善 | extra/spill 增量 B | 新字节命中率 | 同计划 P2/P3 |',
             '|---|---:|---:|---:|---:|---:|---:|']
    for r in rows:
        gain = '未测' if r['cache_gain'] is None else '%.9f' % r['cache_gain']
        lines.append(f"| {r['case_id']}/{r['variant']} | {r['old_makespan']} | {r['new_makespan']} | {r['reduction_percent']:.4f}% | +{r['delta_spill_bytes']} | {r['new_hit_rate']:.9f} | {gain} |")
    lines.extend(['', '四组真实 owner、每核 M/V 操作投影及分区新增 COPY 均保持不变；额外 COPY 增量等于 spill 增量。三组改善、一组退化，四组 spill 均增加。058/forest 的退化保留，按预定规则不追加 P2。', '',
                  '079/band 的原 6165618 周期降到 6006541，消除了相对旧 forest 的退化；但新 forest 前瞻仍快 22357 周期，因此 D 最优分核仍不是 M 最优证明。058/band 组合相对最初 forest 1004819 降到 897619，但该跨 owner 改善不能冒充本表的单因素效应。', '',
                  '前瞻控制仅证明此操作次序变换在上述已见图上的效果。没有重建新 plan 的实际内存边，不能断言每个周期的因果归属；静态前沿多一叶也不等于异步容量证书。保持相同算术工作量不保证 spill、Cache、Makespan 不变。', '',
                  '下一步固定组合构造（分带 DP + 端点树序 + 单叶前瞻），在完整识别族检查剩余预算、重复与下界，并仅由官方 M 决定接受。保留原三次在线 E0 上限；不得拼入旧全500分数或宣称全指标支配。', '',
                  '构造耗时和外部 E0 耗时见 run.json；这不是端到端在线求解时间。comparison.json 可由 `uv run --locked python -m src.q3.leaf_lookahead_report --forest-root FOREST_PRODUCER` 重建，不调用评分器。'])
    (ROOT / AREA / 'REPORT.md').write_text('\n'.join(lines) + '\n')
    print({'comparisons': len(rows), 'new_e0': 0, 'better': sum(r['delta_makespan'] < 0 for r in rows)})


if __name__ == '__main__':
    main()
