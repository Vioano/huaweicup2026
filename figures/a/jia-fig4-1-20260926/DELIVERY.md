# 图 4-1 交付包｜P1 两层决策与官方评价流程（v2 返工版）

- 图号：4-1　版本：v2（2026-09-26，按 #205 评论 5836746442 / 5836853258 返工）
- 主责：甲　输入数据约束：仅 GitHub 仓库固定来源，无外部数据
- 历次修改稿保留：v1/v4（提交 879c3dc3、01425aa3）未被覆盖；本版为新提交

## 文件

| 文件 | 说明 |
|---|---|
| `fig4-1-p1-two-layer-flow.drawio` | 可编辑源（draw.io；本版修复了旧源第 46 行多余 `</mxCell>` 的 XML 缺陷，并按返工意见改图） |
| `fig4-1-p1-two-layer-flow.svg` | 矢量成图（由修复后源重新导出） |
| `fig4-1-p1-two-layer-flow.png` | PNG 预览（scale=2，由修复后源重新导出） |
| `caption.md` | 图注 |
| `self-check.md` | 自查记录（v2，逐项对照返工意见） |
| `nodes.csv` | 逐节点映射（stage 列使用派发模板 required_stages 标准标记） |
| `edges.csv` | 逐边清单（与图中实际连线一一对应，含分支标签） |
| `audit.json` | 自动核验清单（全部随包文件登记 + 真实 SHA256 + 40 位固定提交来源） |

## 图注

见 `caption.md`（v4 补件版已含单候选直达、`--diagnostics` 旁路表述，本版未改动文字内容）。

## 流程节点 ↔ 源码模块对应表（v2 修正定位）

| 图中节点 | 源码模块 | 提交/位置 |
|---|---|---|
| 结构特征识别 | `unified.py`（依赖提取 + 结构识别） | a0537aeb `src/q1/unified.py` |
| 六类候选构造 | `generate_candidates`：bounded / heavy-or-sink / overload / shared-input / capacity-return / fork-frontier；**覆盖/依赖合法性检查发生在各构造器内部严格识别器**（如 capacity-return 的 strict-private-chain-check），不在 plan_bytes | 同上 |
| 字节去重（add() 内） | `plan_bytes`（JSON 序列化实际输出字节）+ SHA-256，重复只保留首个；仅字节去重，不做合法性检查 | 同上 |
| 单/多候选分支 | `solve`：去重后 `len(candidates)==1` → `choose(candidates, None)` 直接选定（single-distinct-plan），**不启动在线 E1**；多候选才构造 `P1BatchEvaluator` | 同上 |
| 在线选优（E1，仅多候选路径） | `src.eval_exact.P1BatchEvaluator`（1 worker / 16 MiB / 60 s / 启动 10 s），按 (Makespan, scheduled COPY bytes) 择优，首个评分失败即停 | 同上 |
| 官方方案文件（严格两字段） | `main --output`：仅 `node_to_subgraph` + `core_schedules` | 同上 |
| 诊断记录旁路 | `main --diagnostics`：独立 JSON，不属官方方案 JSON，不进官方评估器 | 同上 |
| 边界 COPY 重建 → Step1/2/3 → 事件模拟 | 官方评估器 `multicore_cut_evaluate_problem_1.py` + `schedule_step1.py` / `schedule_step2.py` / `schedule_step3.py` | 冻结 `data/raw/a/official/code/` @ a0537aeb |

## 输入数据版本（含真实哈希）

| 来源 | 固定提交 | SHA-256 |
|---|---|---|
| `src/q1/unified.py`（v4 统一入口） | a0537aeb72dc702af86d67d3194587d581ac207c | 3c571f6c9c0ef2a956268abf9129d557f2d087e783b4e621c2917279fa13e985 |
| `paper/sections/P1-问题一论文初稿.md`（4.1、4.4.1~4.4.4） | 67c0f603960fddf86416d23ca3e85e53561c3c3a | 10d0dc195e138c42f7507ca12c8619ebdf46c4df54ca38b31fe353fc886ef8ef |
| `data/raw/a/official/code/multicore_cut_evaluate_problem_1.py` | a0537aeb72dc702af86d67d3194587d581ac207c | 2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f |
| `data/raw/a/official/code/schedule_step1.py` | 同上 | d8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034 |
| `data/raw/a/official/code/schedule_step2.py` | 同上 | 2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3 |
| `data/raw/a/official/code/schedule_step3.py` | 同上 | 50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a |
| `data/raw/a/official/data/config.txt`（Θ：DDR 60 B/cycle；L1 524288 B、UB 131072 B；门控 100/1000 cycles） | 同上 | dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9 |

哈希口径：`git show <commit>:<path>` 的原始字节（与 GitHub 固定 blob 一致），非工作区检出字节。

## 生成与校验命令

- 导出：`"F:/draw.io/draw.io.exe" --disable-gpu --no-sandbox -x -f svg -o fig4-1-p1-two-layer-flow.svg fig4-1-p1-two-layer-flow.drawio`；PNG 加 `-f png -s 2`
- XML 解析：Python `xml.dom.minidom.parse` 通过（旧源第 46 行多余 `</mxCell>` 已修复）

## 已通过的检查（v2）

- [x] 单候选分支：去重后仅 1 个候选 → 直接选定（single-distinct-plan），不启动在线 E1，仍需独立 E0 复评
- [x] 候选箭头：六类候选 → add() 字节去重 → 分支判定 →（多候选）E1；（单候选）直达方案；候选不再绕过去重
- [x] 合法性检查定位：图中与对应表均写明在各构造器内部严格识别器，plan_bytes 仅字节去重
- [x] 方案接口消歧：官方方案文件严格两字段；诊断单独旁支标 `--diagnostics`
- [x] audit.json 登记全部随包文件（含 DELIVERY.md 本文件）与真实 SHA256；来源为 40 位固定提交 + 64 位哈希 + 真实路径
- [x] nodes.csv stage 使用派发模板 required_stages 标准标记（structure/partition/assignment/task_order/candidate_select/online_e1/node_to_subgraph/core_schedules/copy_rebuild/official_schedule/final_e0/makespan/extra_ddr 全覆盖；input/diagnostics 为边界与旁路标记）
- [x] 切图、分核、每核 Task 顺序三项决策齐全；无逐 Pipe 顺序/等待时间控制权
- [x] 在线 E1 与独立 E0 复评分开表示；研究模块未混入主线
- [x] draw.io CLI 重新导出 SVG/PNG；PNG 目检无缺字、无遮挡、无裁切

## 未完成项 / 说明

- 接收端已自行修复的 SVG 声明/HTML 标签兼容问题非本包缺陷；本包以修复后源直接导出，源与成图一致（哈希见 audit.json）。
- 若 P1 初稿或 v4 绑定版本变更，本图随对应版本同步更新。
