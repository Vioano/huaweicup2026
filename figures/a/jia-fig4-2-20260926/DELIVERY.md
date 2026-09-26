# 图 4-2 交付包｜分叉-汇合结构的阶段划分与分核（v7）

- 图号：4-2　版本：v7（2026-09-26，按工作台 #14 评论 5843410556 意见返工；科学三条已于该轮签通过，本轮仅排版/交付记录项；历次稿保留于 git 历史）
- 主责：甲　输入数据约束：仅 GitHub 仓库固定来源（P1 初稿 4.4.2@67c0f603、示例表 e9f3a520、模板@e82c2009），无外部数据

## 本版（v7）修订——逐条对应 5843410556

1. **真实论文页面预览（意见核心项）**：新增 `fig4-2-page-preview-template2026.pdf/.png`——用 **paper/template-2026**（gmcm2026.cls，origin/main@e82c2009，正文宽 165mm/高 248.5mm）实际 XeLaTeX 编译的单页：图以 **152mm 实际插入宽度**（正文宽 92%）放置，配**最终两行图注**（图号"图 4.2"），LaTeX 无 "Float too large" 警告，确认无超页、无裁切、图与图注文字可读。编译源 `page-preview-main.tex` 随包交付。之前仅剩 8.293mm 给图注放不下整段长说明的问题，通过"等比缩放（152mm）+ 精简图注"解决，符合意见允许的口径。
2. **图注精简**：`caption.md` 改为页面预览所用最终两行图注；详细节点/边对应说明保留在 DELIVERY.md 与 nodes.csv/edges.csv，不进论文图注。
3. **self-check 对齐（意见第 3 项）**：重写为 v7——版本号、尺寸与字号统一按最终文件：实际 viewBox 724×1054；纯图按 165mm 宽最小字 ≈6.46pt（主标签 11–12px ≈7.1–7.8pt）；页面预览按 152mm 宽插入时最小字 ≈5.95pt。audit 版本说明同步 v7。
4. **哈希闭环**：图/图注/记录全部定稿后一次性重算 audit.files 全部哈希（含新增 page preview 三个文件），commit→push 后回读远端逐项核对。

## 文件清单

| 文件 | 角色 | 说明 |
|---|---|---|
| `fig4-2-fork-join-partition.svg` / `.png` / `.drawio` | 主图 | 上下组合三面板，viewBox 724×1054 |
| `fig4-2-page-preview-template2026.pdf` / `.png` | **真实页面预览** | template-2026 XeLaTeX 编译，152mm 插入 + 最终图注，单页无超页 |
| `page-preview-main.tex` | 预览编译源 | 可复现（git archive origin/main paper/template-2026 + 本 tex） |
| `caption.md` | 图注 | 最终两行版（与页面预览一致） |
| `nodes.csv` / `edges.csv` | 绘图输入 | 12 节点（id/stage/subgraph/core/order/note）/ 13 边 |
| `preview-insert-width.png` | 物理宽度预览 | 1500px 纯图缩放目检（辅助） |
| `self-check.md` | 自查 | v7 |
| `audit.json` | 机检清单 | figure-auto-review-v1 |
| `*.modern.*` | 美化变体 | 不进入本轮验收 |

## 结构与口径（与已签通过的版本一致，未改动）

- 12 节点三面板恰好覆盖一次；13 条依赖与 (a) 一致；式 (4-11) 阶段划分、完整链前沿保留不切、归约尾合并；K=3 核 Task 次序与依赖相容、联合图无环。
- 图例：灰=阶段 0、绿=完整链前沿、橙=归约尾；蓝实线=同核 Task 次序、金虚线=跨核依赖（经 DDR）。
- 结构示例（自整理，非实测数据）；条块宽度无时间含义；不声称实测加速或零 spill。
- nodes.csv core/order 从 1 开始，图面 Core 0/1/2 对应 CSV 1/2/3（audit.core_convention）。

## 待对方/整稿处理

- 无阻塞项。若整稿侧确定图注用更详版本或整页放置（165mm 全宽需图注 ≤8mm，不放长说明），按整稿决定微调。
