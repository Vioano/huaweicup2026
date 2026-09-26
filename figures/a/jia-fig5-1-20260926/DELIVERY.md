# 图 5-1 交付包｜P2 张量通信优化技术路线（v1）

- 图号：5-1　版本：v1（2026-09-26，按派发单 5843791182 制作）
- 主责：甲（farmeruncle123）　输入数据约束：仅 GitHub 仓库固定提交（P2 初稿@615b1a5f、证据索引 S3/S4@615b1a5f、主算法源码@c66559a6），无外部数据；0 新实验

## 文件清单

| 文件 | 角色 | 说明 |
|---|---|---|
| `fig5-1-p2-tensor-comm-route.svg` / `.png` | 主图 | draw.io CLI 导出（--disable-gpu --no-sandbox），实际 viewBox 762×1053 |
| `fig5-1-p2-tensor-comm-route.drawio` | 可编辑源 | 主线+侧栏分支流程图 |
| `nodes.csv` / `edges.csv` | 绘图输入 | 17 节点（id/stage/note）/ 19 边（含分支条件标注），与 drawio 元素一一对应 |
| `caption.md` | 图注 | 图意、口径、来源、必要局限 |
| `preview-insert-width.png` | 物理宽度预览 | 1500px 插入观感 |
| `self-check.md` | 自查 | v1 |
| `audit.json` | 机检清单 | figure-auto-review-v1，哈希按最终字节重算 |

## 本图对应派发要求

1. **三类候选关系与完整评分出口**：Π₀（结构路由+式 5-7 活跃核）→ 分叉汇合守卫 → Πgap（链收缩+间隙日历，式 5-8）→ 一遍两核区域超图改进（式 5-9，区域≤16 链，Dinic 最小割+逐次锚定+负载上限锚回）→ 基础 COPY 字节严格下降才重排出 Πhypergap → 式 (5-10) 去重 C≤3 → 原生 E2 评分 ≤3 次 → (Makespan, 额外 DDR B) 择优（平局保留先前）→ 两字段方案 → E0 独立复评。
2. **分支/候选保留/评分次数与冻结入口一致**：与 c66559a6 `adaptive_hypergap_guarded.py` 逐行核对——守卫失败保留 Π₀（不构造 gap）；字节下降只决定是否追加 hypergap、不剪掉原 gap（S3）；超图费用无严格下降只省略第三候选；每方案至多 1 次、总计 ≤3 次评分；|C|=1 直接保留不启动 E2；平局保留先前计划；评分异常/未知显式记录。
3. **静态通信目标与最终 Makespan 评价分开**：侧栏「静态估计仅用于构造与优先序」节点显式声明式 (5-7)/(5-9) 与日历时钟非正式成绩、非一般 Makespan 下界；主线 E2/E0 评分出口单独表示。
4. **未接入研究模块不入主线**：侧栏「未接入主线的研究模块清单」（adaptive_direct/adaptive_frontier/vector_*/tree_*/windows_* 等）以开放虚线标注「研究扩展，不参与候选集合与评分」。
5. **侧栏容量与下界诊断**：5.5 节容量闭区间条件与必要下界（命题 2、式 5-14～5-17，S2/S5）标注「仅诊断/解释，不进入候选构造与评分」。

## 已通过的检查（v1）

- drawio-skill validate.py 0 error（33 条 warning 均为布局提示：菱形与容器虚线类，逐条复核无实义交叉残留）。
- 1500px 插入宽度预览逐项目检：无穿字、无遮挡、无裁切、无缺字；三条分支（守卫否/字节否/|C|=1 是）路径与标签清楚。
- 节点/边表与 drawio 源一一对应；关键调用名（adaptive_hypergap_guarded、hypergraph_cost、binary_hypercut、gap_candidate、gap_calendar、gap_retime、adaptive_guarded、adaptive_budget、adaptive_semantic、active_core_wave）与 c66559a6 实际文件名一致。
- 尺寸：viewBox 762×1053；按 165mm 宽插入高 228.0mm、最小字 ≈6.14pt（主标签 11–13px → 6.8–9.0pt）；按 152mm 宽插入高 210.0mm（页面容纳口径与 4-2 一致）。

## 未完成项

- 无。modern 美化变体将于验收通过后基于最终规范版源补出（不进入本轮验收）。
