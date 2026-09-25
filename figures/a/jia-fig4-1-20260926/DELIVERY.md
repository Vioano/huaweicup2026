# 图 4-1 交付包｜P1 两层决策与官方评价流程（v3 返工版）

- 图号：4-1　版本：v3（2026-09-26，按 #14 评论 5837226124 / 5837354904（工作台 Agent 验收意见）返工）
- 主责：甲　输入数据约束：仅 GitHub 仓库固定来源，无外部数据
- 历次修改稿保留：v1/v4（提交 879c3dc3、01425aa3）、v3（ddd9c2425）、上一版（be49466c1）均未被覆盖；本版为新提交，以完整 SHA 为准

## 文件

| 文件 | 说明 |
|---|---|
| `fig4-1-p1-two-layer-flow.drawio` | 可编辑源（draw.io；本版修复了旧源第 46 行多余 `</mxCell>` 的 XML 缺陷，并按返工意见改图） |
| `fig4-1-p1-two-layer-flow.svg` | 矢量成图（由修复后源重新导出） |
| `fig4-1-p1-two-layer-flow.png` | PNG 预览（scale=2，由修复后源重新导出） |
| `fig4-1-preview-insert-146mm.png` | 论文插入宽度预览（等效 A4 `\textwidth`=146.6 mm @300dpi，宽 1734 px） |
| `caption.md` | 图注 |
| `self-check.md` | 自查记录（v3，逐项对照工作台 Agent 验收意见） |
| `nodes.csv` | 逐节点映射（id 与 drawio XML ID 一致；stage 列为单值标准标记，另设 7 行带唯一 ID 的语义子项行覆盖 partition/assignment/task_order/node_to_subgraph/core_schedules） |
| `edges.csv` | 逐边清单（与图中实际连线一一对应，含分支标签） |
| `audit.json` | 自动核验清单（随包文件登记，不含 audit.json 自身 + 真实 SHA256 + 40 位固定提交来源） |

## 图注

见 `caption.md`（v4 补件版已含单候选直达、`--diagnostics` 旁路表述，本版未改动文字内容）。

## 流程节点 ↔ 源码模块对应表（v3：id 与 drawio XML ID 统一）

| 图中节点（XML ID） | 源码模块 | 提交/位置 |
|---|---|---|
| 结构特征识别（identify） | `unified.py`（依赖提取 + 结构识别） | a0537aeb `src/q1/unified.py` |
| 六类候选构造（candBox，子节点 c1~c6） | `generate_candidates`：bounded / heavy-or-sink / overload / shared-input / capacity-return / fork-frontier；**覆盖/依赖合法性检查发生在各构造器内部严格识别器**（如 capacity-return 的 strict-private-chain-check），不在 plan_bytes | 同上 |
| 构造失败语义 | `unified.py add`：可选候选失败跳过；必需 bounded 候选失败（required=True）直接 raise 终止 | 同上 |
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
| `paper/sections/P1-问题一论文初稿.md`（章节定位见 note：4.1、4.4.1~4.4.4） | 67c0f603960fddf86416d23ca3e85e53561c3c3a | 10d0dc195e138c42f7507ca12c8619ebdf46c4df54ca38b31fe353fc886ef8ef |
| `data/raw/a/official/code/multicore_cut_evaluate_problem_1.py` | a0537aeb72dc702af86d67d3194587d581ac207c | 2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f |
| `data/raw/a/official/code/schedule_step1.py` | 同上 | d8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034 |
| `data/raw/a/official/code/schedule_step2.py` | 同上 | 2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3 |
| `data/raw/a/official/code/schedule_step3.py` | 同上 | 50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a |
| `data/raw/a/official/data/config.txt`（Θ：DDR 60 B/cycle；L1 524288 B、UB 131072 B；门控 100/1000 cycles） | 同上 | dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9 |

哈希口径：`git show <commit>:<path>` 的原始字节（与 GitHub 固定 blob 一致），非工作区检出字节。

## 生成与校验命令

- 导出：`"F:/draw.io/draw.io.exe" --disable-gpu --no-sandbox -x -f svg -o fig4-1-p1-two-layer-flow.svg fig4-1-p1-two-layer-flow.drawio`；PNG 加 `-f png -s 2`
- XML 解析：Python `xml.dom.minidom.parse` 通过（旧源第 46 行多余 `</mxCell>` 已修复）

## 已通过的检查（v3）

- [x] nodes.csv 以 csv.writer 规范写出（含逗号字段自动加引号），逐行 4 列无多余字段；id 与 drawio XML ID 统一（candBox、c1~c6），边端点全部存在
- [x] required_stages 以单独 stage 单值登记：partition/assignment/task_order/node_to_subgraph/core_schedules 各有唯一 ID 行（语义子项，note 注明对应 XML ID，非虚构图节点）
- [x] 候选大框头部两行说明不与第一排候选框重叠；strict-private-chain-check 等源码解释移至图内 note3 与对应表
- [x] 构造失败语义改为准确表述：可选候选失败跳过；必需 bounded 失败终止（required=True 时 raise）
- [x] 官方方案→read 虚线改走诊断框外侧（经折线绕行），诊断框移位后两条输出（方案文件 / 诊断 JSON）独立可辨
- [x] 插入宽度检查：按 A4 `\textwidth`=146.6 mm（gmcmthesis.cls，left/right=31.7 mm）预览目检，结论见 self-check.md
- [x] audit.json 登记全部随包文件（不含 audit.json 自身）与真实 SHA256；来源为 40 位固定提交 + 64 位哈希 + 真实仓库路径（章节定位放 note）
- [x] 切图、分核、每核 Task 顺序三项决策齐全；无逐 Pipe 顺序/等待时间控制权
- [x] 在线 E1 与独立 E0 复评分开表示；研究模块未混入主线
- [x] draw.io CLI 重新导出 SVG/PNG；PNG 目检无缺字、无遮挡、无裁切

## 未完成项 / 说明

- 接收端已自行修复的 SVG 声明/HTML 标签兼容问题非本包缺陷；本包以修复后源直接导出，源与成图一致（哈希见 audit.json）。
- 若 P1 初稿或 v4 绑定版本变更，本图随对应版本同步更新。
