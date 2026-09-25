# 图 4-1 自查记录（甲，v2 返工版，2026-09-26）

对照乙返工意见（#205 评论 5836746442 图面 4 项 + 5836853258 补件 3 项 + 源缺陷 1 项）逐项：

## 图面（5836746442）

1. 单候选分支 → 已加：dedup 后新增菱形判定节点「solve：去重后候选数 = 1？」；「仅 1 个候选」→ 直接选定框（choose：single-distinct-plan，不启动在线 E1，仍需独立 E0 复评）→ 方案；「多个候选」→ 在线 E1。依据固定源 `solve()`：`len(candidates)==1` 时 `choose(candidates, None)`，不构造 P1BatchEvaluator。
2. 候选/去重箭头 → 已改：结构识别 → 六类候选框 →（构造 plan → add()）→ 字节去重 → 分支判定；六候选不再直接连 E1。dedup 节点文字与对应表写明：合法性检查发生在各构造器内部严格识别器（如 capacity-return strict-private-chain-check），plan_bytes 仅做输出字节 SHA-256 去重。
3. 方案接口消歧 → 已改：金色框改为「官方方案文件 P（main --output，磁盘传递）—— 严格只含两个字段 node_to_subgraph｜core_schedules，不含任何诊断内容」；诊断单独旁支虚线框标 `--diagnostics`（独立 JSON，不属官方方案 JSON，不进官方评估器）。
4. 机器可核验材料 → 见补件部分。

## 补件（5836853258）

1. 文件清单 → audit.json `files` 登记全部随包文件（svg/png/drawio/caption/self-check/nodes.csv/edges.csv/DELIVERY.md），各带真实 64 位 SHA256；audit.json 为清单本体，自引用哈希不可行，特此说明。
2. 来源身份 → `sources` 每项为 40 位固定提交 + 真实文件路径 + 64 位 SHA256（`git show <commit>:<path>` 原始字节口径，与 GitHub 固定 blob 一致）。
3. nodes.csv stage → 使用派发模板 required_stages 标准标记，13 项全覆盖：structure=identify；partition/assignment/task_order=cand_box 与 c1~c6；candidate_select=dedup/decision/single；online_e1=e1；node_to_subgraph;core_schedules=plan/read；copy_rebuild=copy；official_schedule=steps/sim；final_e0=e0；makespan=out1；extra_ddr=out2。另有 input（in，输入边界）、diagnostics（diag，旁路）两个非算法阶段标记，未虚构图中不存在的节点。
4. 源文件 XML 缺陷 → 旧源第 46 行多余 `</mxCell>` 已删除；`xml.dom.minidom` 解析通过；SVG/PNG 由修复后源重新导出并更新哈希，源与成图一致。

## 常规项

- 三项决策齐全、E1/E0 分开、研究模块未混入：保持 v1 结论，v2 图面继续满足。
- 工具：draw.io CLI 导出（--disable-gpu --no-sandbox；svg 与 png -s 2）；XML minidom 解析通过。
- 版面：PNG（scale=2）目检——分支标签「仅 1 个候选/多个候选」清晰，无文字被线条遮挡，无裁切；诊断旁路框与下层容器不重叠。
- 有效/缺失数量：流程节点 22（in/identify/cand_box+c1~c6/dedup/decision/single/e1/plan/diag/read/copy/steps/sim/e0/out1/out2），连线 16（与 edges.csv 一一对应）；无缺失输入。
- 未完成项：无。
