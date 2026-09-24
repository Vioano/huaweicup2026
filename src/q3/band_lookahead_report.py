"""Reconstruct family tradeoffs and fresh integration evidence, without E0."""
import argparse
from collections import Counter
from pathlib import Path

from .construct import ROOT
from .feedback_benchmark import digest, git_bytes, read, validate_result, write
from .leaf_lookahead_probe import FOREST_COMMIT

FAMILY = 'results/a/q3-nikolastarx/band-lookahead-family-20260925'
ONLINE = 'results/a/q3-nikolastarx/band-lookahead-online-20260925'


def counts(rows):
    return {key: {'less': sum(r[key] < 0 for r in rows),
                  'equal': sum(r[key] == 0 for r in rows),
                  'greater': sum(r[key] > 0 for r in rows),
                  'sum_delta': sum(r[key] for r in rows)}
            for key in ('delta_M', 'delta_extra_bytes', 'delta_spill_bytes',
                        'delta_hit_bytes', 'delta_hit_rate')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--forest-root', required=True, type=Path)
    args = parser.parse_args()
    run = read(ROOT / FAMILY / 'run.json')
    assert run['status'] == 'complete'
    assert len(run['records']) == len({(r['case_id'], r['cores']) for r in run['records']}) == 50
    for path, sha in run['source_input_sha256'].items():
        assert digest(ROOT / path) == sha
    rows = []
    for r in run['records']:
        rp = Path(r['baseline_receipt'])
        assert (args.forest_root / rp).read_bytes() == git_bytes(args.forest_root, FOREST_COMMIT, str(rp))
        receipt = read(args.forest_root / rp)
        path = args.forest_root / rp.parent / 'result.json.gz'
        assert digest(path) == receipt['result_sha256'] == r['baseline_result_sha256']
        baseline = read(path)
        assert baseline['makespan'] == r['baseline_makespan']
        assert baseline['data_movement_bytes'] == r['baseline_movement']
        assert baseline['cache_stats'] == r['baseline_cache_stats']
        if 'makespan' not in r:
            continue
        assert digest(ROOT / r['plan_path']) == r['plan_sha256']
        assert digest(ROOT / r['result_path']) == r['result_sha256']
        new = read(ROOT / r['result_path'])
        assert new['problem'] == 3 and new['scene'] == 'B' and new['cache_mode'] == 'read_only'
        assert new['num_cores'] == r['cores'] and new['makespan'] == r['makespan']
        assert new['data_movement_bytes'] == r['movement'] and new['cache_stats'] == r['cache_stats']
        lower = r.get('lower_bound_cycles')
        assert lower is None or lower <= new['makespan']
        rows.append({'case_id': r['case_id'], 'cores': r['cores'], 'evidence': r['status'],
                     'old_M': baseline['makespan'], 'new_M': new['makespan'],
                     'delta_M': new['makespan']-baseline['makespan'],
                     'delta_extra_bytes': r['movement']['added_copy_bytes']-r['baseline_movement']['added_copy_bytes'],
                     'delta_spill_bytes': r['movement']['spill_added_copy_bytes']-r['baseline_movement']['spill_added_copy_bytes'],
                     'delta_hit_bytes': r['cache_stats']['hit_bytes']-r['baseline_cache_stats']['hit_bytes'],
                     'delta_hit_rate': r['cache_stats']['hit_rate']-r['baseline_cache_stats']['hit_rate'],
                     'fixed_plan_lower_bound': lower,
                     'gap_over_fixed_plan_bound_percent': 100*(new['makespan']/lower-1) if lower else None})
    strict = [r for r in rows if r['delta_M'] < 0]
    summary = {'source_commit': run['source_commit'], 'statuses': dict(Counter(r['status'] for r in run['records'])),
               'new_P3': run['new_p3'], 'historical_exact_reuse': run['historical_reused'],
               'batch_wall_seconds': run['elapsed_seconds'], 'scored_count': len(rows),
               'all_scored_tradeoffs': counts(rows), 'strict_M_improvement_count': len(strict),
               'strict_M_improvement_tradeoffs': counts(strict), 'rows': rows,
               'scope': 'recognized family only; no merged full500 score, no new solver time from this probe'}
    write(ROOT / FAMILY / 'comparison.json', summary)
    lines = ['# 分带与单叶前瞻：完整识别族的正负结果', '',
             f"固定源码 `{run['source_commit']}`。10 张已见图×1–5 核，50 个唯一位置；45 新 P3 + 2 份字节身份精确复用，2 个静态下界剪枝、1 个原三次预算耗尽。整批 {run['elapsed_seconds']:.6f} 秒，1 worker、0 solver、0 retry。预检另用26.783380秒，0E0。", '',
             '47 个已评分候选：21 改善、14 持平、12 退化；若无官方 M 回退，候选周期差合计反而为 +244619。因此不能默认使用新构造，更不能只留下正例。', '',
             '| 指标 | 全47格减少/持平/增加 | 仅21个严格M改善格：减少/持平/增加 |',
             '|---|---|---|']
    for name, key in [('Makespan', 'delta_M'), ('extra COPY bytes', 'delta_extra_bytes'),
                      ('spill bytes', 'delta_spill_bytes'), ('Cache hit bytes', 'delta_hit_bytes'),
                      ('Cache byte hit rate', 'delta_hit_rate')]:
        a, b = counts(rows)[key], counts(strict)[key]
        lines.append(f"| {name} | {a['less']}/{a['equal']}/{a['greater']} | {b['less']}/{b['equal']}/{b['greater']} |")
    lines.extend(['', '严格M改善子集共减少834872 cycles、730933248 extra COPY bytes和649160704 spill bytes；但021/2的extra增加1019904B，021/2、039/5、058/3、058/5的spill增加。12格字节命中率下降，不能称全指标支配；减少重复搬运会改变命中率分母，命中率下降也不能单独断定物理搬运变差。此处不计算虚构的官方加权总分。', '',
                  '| 图 | 核数 | 原 M | 新 M | Δextra B | Δspill B | Δ字节命中率 | 固定计划下界差距 |',
                  '|---|---:|---:|---:|---:|---:|---:|---:|'])
    for r in strict:
        gap = '未证' if r['gap_over_fixed_plan_bound_percent'] is None else f"{r['gap_over_fixed_plan_bound_percent']:.4f}%"
        lines.append(f"| {r['case_id']} | {r['cores']} | {r['old_M']} | {r['new_M']} | {r['delta_extra_bytes']} | {r['delta_spill_bytes']} | {r['delta_hit_rate']:.6f} | {gap} |")
    lines.extend(['', '下界固定了该方案的 owner 与 M/V FIFO 次序，是此计划的条件下界；不是对任意分核/切图的全局最优证书。059/1距离该界只有173周期（约0.0234%），仍不能据此宣布整题最优。所有未改进格和未评分状态见comparison.json/run.json。', '',
                  '统一在线入口为src.q3.band_lookahead_solve：fresh forest作为控制，有剩余三次总预算才尝试这一份构造，先去重/下界剪枝，仅更低官方M接受。下一步需验证同一源码入口完整100×1–5新运行；本报告不能把21个历史赢家拼入旧forest500，也不替代同计划无L2对照。'])
    from .band_gap_report import audit
    target = next(r for r in run['records'] if r['case_id'] == '097' and r['cores'] == 1)
    old_path = args.forest_root / Path(target['baseline_receipt']).parent / 'result.json.gz'
    graph = read(ROOT / 'data/raw/a/official/data/case_097.json')
    gaps = {'scope': 'observed timeline only; no prepared memory edges or causal proof; zero E0',
            'old_forest': audit('old_forest', read(old_path), graph, 0),
            'new_band_lookahead': audit('new_band_lookahead', read(ROOT / target['result_path']), graph, 0)}
    write(ROOT / FAMILY / '097-k1-gap.json', gaps)
    a, b = gaps['old_forest']['summary'], gaps['new_band_lookahead']['summary']
    assert a['busy_M'] == b['busy_M'] and a['first_M_start'] == b['first_M_start'] and a['tail_after_M'] == b['tail_after_M']
    assert b['internal_M_gaps']-a['internal_M_gaps'] == target['delta_makespan']
    lines.extend(['', '## 最大退化097/1的下一步线索', '',
                  '原M10746146→新11215134，增加468988周期。M忙碌工作10303488、启动172、最后M后的尾部613都相同；全部差额来自M内部空隙441873→910861。新方案最大单次空隙反而从1224降到546，所以只优化最大空隙会误导，必须看整条管线的累计等待。', '',
                  '新方案最大的三处间隙各有一个按logical tensor匹配的可见COPY_IN恰在后继M开始时完成。这是输入就绪线索，没有匹配全部incarnation/实际复用边，不是因果证明。读原时间线不调用E0。下一步优先分析重复输入就绪与复用依赖的触发频率，不增加任意前瞻深度扫描。'])
    (ROOT / FAMILY / 'REPORT.md').write_text('\n'.join(lines)+'\n')

    batch = read(ROOT / ONLINE / 'run/batch.json')
    assert batch['status'] == 'stage_complete'
    online = []
    for r in batch['records']:
        assert r['status'] == 'ok'
        folder = ROOT / Path(r['run_path']).parent
        result, receipt, artifacts = validate_result(folder, r)
        assert artifacts == r['artifacts']
        assert receipt['official_e0_calls'] == r['calls']['E0'] <= 3
        assert result['makespan'] == r['makespan_cycles']
        expected = next((x for x in rows if x['case_id'] == r['case_id'] and x['cores'] == r['cores']), None)
        if expected and expected['delta_M'] < 0:
            assert result['makespan'] == expected['new_M']
        online.append({'case_id': r['case_id'], 'cores': r['cores'], 'M': result['makespan'],
                       'online_E0': r['calls']['E0'], 'solver_wall_seconds': r['solver_process']['wall_seconds'],
                       'policy': receipt['seed_selection']['band_lookahead_policy']['status']})
    write(ROOT / ONLINE / 'audit.json', {'source_commit': batch['solver_commit'], 'fresh_solvers': len(online),
          'online_E0': sum(r['online_E0'] for r in online), 'batch_wall_seconds': batch['elapsed_wall_seconds'],
          'rows': online, 'all_artifacts_and_call_ledgers_verified': True, 'new_e0_from_audit': 0})
    lines = ['# 五格 fresh solver 集成验证', '',
             '冻结入口与源码同完整识别族；5 新求解进程、12 在线 E0，0 retry，1 worker。整批49.291143秒。实例覆盖非Cartesian回退、下界剪枝、M改善但次指标退化、组合构造正例及较大单核图。', '',
             '| 图 | 核数 | M | 在线E0 | 求解墙钟秒 | 新候选策略状态 |', '|---|---:|---:|---:|---:|---|']
    for r in online:
        lines.append(f"| {r['case_id']} | {r['cores']} | {r['M']} | {r['online_E0']} | {r['solver_wall_seconds']:.6f} | {r['policy']} |")
    lines.extend(['', '墙钟覆盖新进程启动、读图、所有候选与在线E0、写盘退出；父预检另含在批墙钟。单次共享主机观测，不等于OS冷缓存、尾延迟分布或跨机器提速。未拆出外部最终E0；在线E0已计入求解耗时。回读计划/结果/收据哈希及实际调用账均通过。', '',
                  '这是统一入口集成检查，不是新的500格成绩。021/2按主指标接受仍伴随extra/spill增长，必须在全量报告保留。原公开100图全部已见，不能宣称泛化验证。'])
    (ROOT / ONLINE / 'REPORT.md').write_text('\n'.join(lines)+'\n')
    print({'family_scored': len(rows), 'M_improved': len(strict), 'fresh_solvers': len(online),
           'online_E0': sum(r['online_E0'] for r in online), 'new_E0_from_report': 0})


if __name__ == '__main__':
    main()
