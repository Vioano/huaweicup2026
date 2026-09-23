# change_impact.md — 变更影响面

run：`r1-20260923-farmeruncle123`｜用途：任何改动进入共享分支前，先按本表判断会波及哪些规则、
夹具与已发布的观察数值。表里只写**已由源码或探针确认**的因果，推断项单独标注。

## 1. 官方材料变更

| 变更 | 直接影响 | 需重跑的证据 | 备注 |
|---|---|---|---|
| `data/config.txt` 任一数值 | F-TIME-001/002、F-RESOURCE-001、F-METRIC-001 | `verify_time_r1.py`、`build_dev_samples.py` | 文件首行标注"不得修改"；改则所有 makespan 数值不可比 |
| `code/schedule_step1.py::step1_from_adj`（key / start_key） | F-LOCAL-001/002 | `verify_local_r1.py`、`verify_ftask_r1.py`、`verify_order_r1.py` | 排序方向极易读反：`-id` 与 `¬is_copy_*` 叠加 LIFO 后效果与直觉相反 |
| `code/schedule_step3.py::_op_duration` | F-TASK、F-METRIC、搬运取整 | `verify_ftask_r1.py`、`build_dev_samples.py` | COPY 时长 = `max(1, ceil(Σsize/bandwidth))` |
| `code/schedule_step3.py::PIPES` / `PIPE_SLOTS` | F-LOCAL-003、F-TIME-002、F-RESOURCE-001 | `verify_local_r1.py`、`verify_time_r1.py` | `PIPE_SLOTS=1`，同 Pipe 串行；改值会改变所有 makespan |
| `code/schedule_step3.py::_uses_ddr_bandwidth` | F-RESOURCE-001/002、F-TIME-002 | `verify_time_r1.py` | 决定谁进 DDR 争用池 |
| `code/stub_multicore_cut_and_schedule.py::derive_multicore_plan` | F-PLAN 全部 6 条 | `verify_rules_r1.py`、`add_fplan005_fixture.py` | 商图成环判定在此 |
| `code/multicore_cut_evaluate_problem_1.py::_build_scene_a_tasks` | F-TASK 全部 4 条 | `verify_ftask_r1.py`、`verify_order_r1.py` | 生成 id 分配、DDR→UB 改写、边界判定 |
| `code/multicore_cut_evaluate_problem_1.py::evaluate_scene_a` 事件循环 | F-TIME-001/002、F-RESOURCE-001 | `verify_time_r1.py` | 等待插入与 DDR 回溯重算都在此 |
| `code/evaluation_validation.py::validate_task_order` / `validate_execution` | F-EXEC-001/002 | `verify_fexec_r1.py` | 报错串里的边标签是判据来源 |
| `docs/a/source-manifest.json` | 所有 `sources[].sha256` | `build_coverage.py` | 规则卡哈希随清单更新；哈希不符会静默失效，需显式比对 |
| `.gitattributes`（`data/raw/a/**`） | 材料解包链路 | `scripts/a_materials.py --extract` | 队长提交 `1dbca4e` 修复 CRLF；再改需重验 |

## 2. 规则变更

| 变更 | 影响 |
|---|---|
| 规则卡 `status` 由 `draft-sourced` 升为 `verified-by-probe` | 必须同步 `formal/coverage.json`（由 `src/adversarial/build_coverage.py` 重新生成），否则两处状态不一致 |
| 新增机制组覆盖 | 需同时更新 `coverage.json` 的 `mechanism_groups` 与 `formal/SPEC.md` 的模块状态表 |
| 修改 `title`/`predicted_by_contract` | 属语义变更，需在 `INCREMENT-*` 回报中说明，不能静默改 |

## 3. 方案层面的已知陷阱（改动前必须知道）

以下四条都来自实测，若代理实现或改进算法按直觉处理，会得到与官方评估器不同的结论：

1. **空核计入核数**（F-PLAN-004/005）。按"非空核"实现会系统性偏大/偏小。
2. **生成 id 的 op 与 tensor 共用同一避让集合**（F-TASK-001）。分配顺序会互相影响，
   不可把两套 id 空间分开处理。
3. **DDR 完成时刻可被回溯推迟**（F-RESOURCE-001）。任何增量式"发放即定局"实现都错。
4. **只有端点含 DDR 的 COPY 进争用池**（F-RESOURCE-002）。一律计 DDR 会高估压力。

## 4. 禁止的推断方向（限制条件第 4 条要求的对偶面）

任务卡明确要求"重编号、交换核心、加核、增 Cache 等变换不得未经证明断言指标不变或改善"。
本批可提供的**反例**仅一条：

- **加核不保证提速**：单链 1 核 makespan=24；两条独立链 2 核 makespan=44（见
  `results/a/form/r1-20260923-farmeruncle123/time-resource-observations.json`）。
  该反例只在微型构造图上成立，**不足以**证明正式用例也如此。

**交换核心、重编号、增 Cache 三类变换我尚未构造任何反例或正例**，因此在本批中不对其
做任何断言。凡后续规则或论文段落涉及这三类变换，都必须先补对应探针。

## 5. 未验证项（不得在改动说明中当作已知）

- `PIPE_SLOTS` 的取值及其对 makespan 的影响。
- L2 带宽是否与 DDR 带宽互不占用（Problem 3 未实测）。
- spill 触发条件的完整刻画；本批未取得 `>=1 spill` 的成功运行。
- F-METRIC-001 五个搬运字段之间的等式关系（仅读源码）。
- 正式 100 个 case 上的任何数值结论——本批全部实测都在微型构造图上完成。
