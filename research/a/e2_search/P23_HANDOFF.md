# E2 问题 2 / 3 适配检查点

本分支承接 PR42 的 P1 固定基线。原 P1 内核、原 PR42 和 Windows/LYX 测试安排不变。

## P2 接口

```python
from research.a.e2_search import SceneBEvaluator, E2BatchEvaluator, read_config
config = read_config("data/raw/a/official/data/config.txt", problem=2)
evaluator = SceneBEvaluator(graph, problem=2, cache_bytes=16 << 20)
record = evaluator.evaluate_record(plan, **config)
# full=True: 本问题冻结 E0 的完整结果保存在 record["result"]，不是加速输出。
# 正式进程脚本需 __main__ 保护：
with E2BatchEvaluator(graph, problem=2, workers=1, timeout_seconds=60) as pool:
    for record in pool.evaluate_batch(plans, **config):
        pass
```

先 `uv sync --locked`、`python scripts/a_materials.py --extract`，再显式构建：
`uv run python -m research.a.e2_search.build_native --problem 2`。
JSONL 搜索 CLI 在原参数上增加 `--problem 2`。无本地库时 `route=e0_fallback`；
`full=True` 为 `e0_full`。不会回退到 P1，不会编译/安装依赖。成功原生评分为 `native`。

P2 每核合并 Task；完整有序 plan、带宽、容量进入缓存键。改核归属/顺序即重建。
缓存上限只约束保留的编译对象，不是进程硬 RSS；原生无内部线程，worker 数显式指定。
输入非法、运行错误、worker 超时/崩溃分列，fallback 保留官方异常类型和文本。
最终优选仍需 E0；不可据此改写已完成 Q2 的基线/预算。

## 第一检查点证据

`results/a/proxy/e2-p2-20260924/`：004/005 各 16 个不同候选，各 4 种划分。
32 个候选三评分字段和全部操作起止时间均与官方一致；8 次 shortlist E0 完整重核一致。
总计 40 次正式 E0，零失败；6 组合成/P2生命周期检查与 8 组 P1 回归通过。

| 16 候选 / 单进程 | 官方完整 E0 | E2 冷方案 | 相对 E0 |
|---|---:|---:|---:|
| 004 | 1.252 s | 1.652 s | 0.76× |
| 005 | 6.692 s | 6.134 s | 1.09× |

初始化/本地库首次载入计入冷时间；后者可能影响首池。官方内部生成完整诊断，E2 输出搜索记录，
因此此表不是相同完整输出吞吐或对应优化 E1 的门槛。热重复为完全相同的 16 方案再次回放，
不能当成新候选吞吐。局部编译占主要成本，未达到优秀的冷搜索加速。
这是 macOS ARM64 开发者对照，不是独立测试/Windows/全100图或最终验收。

`as-run-source.zip` 每个成员都与 run.json 的实测源码 SHA-256 一致，原始 E0 结果保留无损 gzip；
后续修改不得覆盖此证据。P3 尚未在本检查点开放，下一步在 P2 已验证语义上增加 FIFO Cache。

## P2 局部编译优化增量

`results/a/proxy/e2-p2-localopt-20260924/` 使用相同 32 个方案再核一次，另 40 次 E0（本任务累计80）。
私有 Step3 副本用计数器替换每事件全表完成扫描，省略未被多核阶段消费的日志，并使用已守卫的平坦图复制。
源码哈希和 AST 形状均守卫，官方内存补边/调度/验证保留；完整和回退路径使用另一份未优化 E0。
所有分数和操作时间再次一致；004 冷 1.619s 对 E0 1.254s（0.77×），005 冷4.581s 对7.059s（1.54×）。
004 含首载约0.7s固定开销，不隐藏它；大批量摊薄效果需要另测，不能把热重复说成冷搜索。
筛选16→官方复核前4的总耗时为1.950s / 6.294s，仍不是“超高速新候选”验收。

测后加固：局部优化构造失败时退回未改官方；新增 CLI problem路由/合法非法合法序列及完整局部编译契约比较，
7组 P2 测试通过，0新增正式E0。原生评分算法未改变。合成测试经历一次字段命名修正、
一次 AST 工具字段调用修正；失败与重试不隐藏，各轮正式结果目录没有失败调用。
