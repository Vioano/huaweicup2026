# 图 4-1 交付包｜P1 两层决策与官方评价流程

- 图号：4-1　版本：v3（2026-09-26；v1 退回后修订，历次稿保留于 git 历史）
- 主责：甲　输入数据约束：仅 GitHub 仓库固定来源，无外部数据

## 文件

| 文件 | 说明 |
|---|---|
| `fig4-1-p1-two-layer-flow.drawio` | 可编辑源（draw.io，双层布局手排，节点间距按论文插入宽度校核） |
| `fig4-1-p1-two-layer-flow.svg` | 矢量成图 |
| `fig4-1-p1-two-layer-flow.png` | PNG 预览（scale=2） |

## 图注（草稿）

图 4-1 给出问题一的两层决策与官方评价流程。上层为完整算法 v4（统一入口 `src/q1/unified.py`，提交 a0537aeb）：从原始计算图 G、核数 K 与冻结配置 Θ 出发，识别弱连通分量、Pipe 工作量（式 4-10）、分叉阶段（式 4-11）、共享输入与同型链等结构特征，由统一入口构造至多六个结构候选（完整分量+有界树前沿、重分量+独占后缀、超载分量分解、输入预算+活跃核选择、容量约束回转分组、分叉阶段前沿）；经覆盖与联合依赖检查并按方案输出字节 SHA-256 去重后，以固定 E1 在线评分按 (Makespan, scheduled COPY bytes) 择优，评分失败即停止并保留已知最好。上层仅输出两个规定字段 `node_to_subgraph` 与 `core_schedules` 组成的方案文件及诊断记录。下层为提交者不可修改的冻结官方评估器（`data/raw/a/official/code/multicore_cut_evaluate_problem_1.py`）：按方案重建 Task 边界 COPY，依次执行官方核内调度 Step1（拓扑顺序）、Step2（缓存换入/换出）、Step3（四 Pipe 时间线），再做多核事件模拟（DDR 共享 60 B/cycle，同核/跨核 Task 门控 100/1000 cycles），给出 Makespan（cycles）与额外数据搬运量（B）两个评价出口。实验阶段另以未修改的 E0 独立复评最终方案，与上层在线 E1 评分分开表示。提交者仅决定切图、分核与每核 Task 顺序三项；逐 Pipe 执行顺序、缓存换入换出与模拟时间线均由冻结评估器确定。研究性扩展（变宽分组、错峰融合等）不属于本主线。

## 流程节点 ↔ 源码模块对应表

| 图中节点 | 源码模块 | 提交/位置 |
|---|---|---|
| 结构特征识别 | `unified.py`（依赖提取）+ 结构识别器 | a0537aeb `src/q1/unified.py` |
| 六类候选构造 | `generate_candidates`：bounded / heavy-or-sink / overload / shared-input / capacity-return / fork-frontier | 同上 |
| 覆盖检查 + 字节去重 | `plan_bytes`（SHA-256） | 同上 |
| 在线选优（E1） | `choose` + `src.eval_exact.P1BatchEvaluator`（1 worker / 16 MiB / 60 s / 启动 10 s） | 同上 |
| 方案与诊断写出 | `main`（`--output` 方案两键；`--diagnostics` 诊断） | 同上 |
| 边界 COPY 重建 → Step1/2/3 → 事件模拟 | 官方评估器 `multicore_cut_evaluate_problem_1.py` + `schedule_step1.py` / `schedule_step2.py` / `schedule_step3.py` | 冻结 `data/raw/a/official/code/` |

## 输入数据版本

- P1 初稿 4.1、4.4.1～4.4.4：提交 67c0f603960fddf86416d23ca3e85e53561c3c3a（`paper/sections/P1-问题一论文初稿.md`）
- 完整算法 v4：提交 a0537aeb72dc702af86d67d3194587d581ac207c（`src/q1/unified.py`）
- 官方评估器与配置：`data/raw/a/official/`（冻结原件，DDR 60 B/cycle；L1 524288 B、UB 131072 B；同核/跨核 Task 等待 100/1000 cycles）

## 已通过的检查

- [x] 切图、分核、每核 Task 顺序三项决策齐全；图中明确提交者无逐 Pipe 顺序与等待时间控制权
- [x] 在线 E1 评分与独立最终 E0 复评分开表示（上/下层分别标注）
- [x] 研究模块（变宽分组、错峰融合等）未混入 v4 主线，图注与对应表均注明
- [x] `validate.py`（drawio-skill）：0 error
- [x] PNG 全宽目检：无缺字、无遮挡、无裁切；中文正常渲染
- [x] 两个提交字段与两个评价出口均已强调标出

## 未完成项 / 说明

- 本图为甲的 drawio 样板：字体（Microsoft YaHei）、双层配色（上层蓝=求解器决策，下层橙=官方评价）、金色=方案文件接口。后续 4-2、5-1、6-1 等结构图沿用此规范。
- 若 P1 初稿或 v4 绑定版本变更，本图随对应版本同步更新，不把局部研究模块画入主线。
