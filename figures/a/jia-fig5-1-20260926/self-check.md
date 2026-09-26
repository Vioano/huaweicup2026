# 图 5-1 自查记录（甲，v1，2026-09-26）

## 依据

- 派发单：#14 评论 5843791182（图 5-1 P2 张量通信优化技术路线）；任务书 v5（SHA256 55859ab1…）。
- 输入：P2 初稿 5.4 全节 @615b1a5f（paper/sections/a-q2.md）；证据索引 S3/S4（附 S2/S5 侧栏素材）@615b1a5f（paper/sections/a-q2-evidence.md）；主算法源码 @c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f（adaptive_hypergap_guarded.py 主入口 117 行逐行读，gap_candidate/gap_hyperrefine/gap_retime 已抓取核对）。
- 实际导出：SVG viewBox 762×1053；165mm 宽插入高 228.0mm；最小字 10px→6.14pt、主标签 11–13px→6.8–9.0pt（fontSize×165/宽×72/25.4 换算）。
- 生成命令：见 audit.json.command。

## 验收标准逐项自查

1. **分支、候选保留和评分次数说明与冻结入口一致** → 通过：guard 否→仅 Π₀；dec 否→省略第三候选但保留 Πgap（S3 声明节点在主线底部）；|C|=1 直接保留不评分；评分 ≤3 次、平局保留先前、异常/未知显式记录——均与 adaptive_hypergap_guarded.py 实现及式 (5-10) 一致。
2. **静态张量通信目标与最终 Makespan 评价分开；不将局部最小割表述为全局调度最优** → 通过：侧栏 stat 节点声明静态估计非正式成绩/非下界；主线评分出口为 E2（在线）与 E0（独立复评）两类完整评价；select 节点标注"候选集合内比较性质，非全局最优性证明"；hyper 节点标注"静态基础 COPY 字节目标（非完整执行时间）"。
3. **尚未接入的容量保护/就绪匹配等研究模块不画入主线** → 通过：research 侧栏节点列清单并以开放虚线连接 route，标注"不参与候选集合与评分"；主线无任何研究模块节点。

## 交付包完整性

- SVG/PNG/.drawio/nodes.csv(17 行)/edges.csv(19 行)/caption.md/DELIVERY.md/self-check.md/audit.json（figure-auto-review-v1，哈希最后统一重算，不含 audit.json 自身）。
- 数值可复核：图中无统计数据节点；仅出现算法结构量（≤6→本图 ≤3 候选、≤16 链、k² 核心对、式编号）均来自初稿 5.4/5.5 原文与固定源码。

## 历史稿区分

- v1 为本图首版（旧图不计数，按派发单重新制作）。

未完成项：无（modern 变体验收后补，不入本轮）。
