# 图 4-1 交付包｜P1 两层决策与官方评价流程（v7）

- 图号：4-1　版本：v7（2026-09-26，按工作台 #14 评论 5843410014 的四项意见返工；历次稿 v1=879c3dc3、补件=01425aa3、v3=ddd9c242、夜班=be49466c1/a2502108、v4=c44e4d40、v5=dc13fac2a、v6=2a03d2972/9749a0963 均保留于 git 历史）
- 主责：甲　输入数据约束：仅 GitHub 仓库固定来源（P1 初稿@67c0f603、v4@a0537aeb、官方评估器冻结原件），无外部数据

## 本版（v7）图面修订——逐条对应 5843410014

1. **candBox→dedup 连线（意见 1）**：f3 出口锚点由顶边（exitX=0.5;exitY=0）实际改为**底边**（exitX=0.5;exitY=1），折点走 candBox 底边（y=224）与 dedup 顶边（y=234）之间的空隙（y=229），不再从候选框顶端纵穿"六类候选构造"标题与框内部。
2. **下层标题带（意见 2）**：下层标题（"下层｜官方评价 — 冻结评估器 multicore_cut_evaluate_problem_1.py（提交者不可修改）"）独立留白带加高——read/copy/steps/sim 及两个评价出口整体下移 16px，layerBottom 容器加高至 268px，标题下沿与 steps 顶边（现 y=430）脱离接触；实际 viewBox 710×689（draw.io CLI 导出，含边缘），按 165mm 宽插入高 160.0mm。
3. **E1→方案折线（意见 3）**：f6b 改由 E1 右边中点出（exitX=1;exitY=0.5），经 x=710（诊断框右缘之外）下行至 y=344 再入方案文件顶边（entryX=0.7），**绕诊断框外缘**，不穿"--diagnostics"文字；诊断虚线（single→diag）与方案实线可辨。
4. **交付记录（意见 4）**：DELIVERY.md 本版全量重写（此前停留在 v3 字节，SHA256 7f988778… 已作废）；self-check.md 重写为 v7，正文与本版真实状态一致；来源对应表见 audit.json.sources（真实 40 位 commit + 64 位 SHA256）。所有"无穿字/无遮挡"结论均以本轮重导出 PNG/SVG 目检为准。

## 文件清单

| 文件 | 角色 | 说明 |
|---|---|---|
| `fig4-1-p1-two-layer-flow.svg` | 主图 SVG | draw.io CLI 导出（--disable-gpu --no-sandbox） |
| `fig4-1-p1-two-layer-flow.png` | 主图 PNG | scale=2 |
| `fig4-1-p1-two-layer-flow.drawio` | 可编辑源 | 本版图面（v7） |
| `caption.md` | 图注 | 完整长图注（含源码模块对应说明），论文中放图注或正文 |
| `nodes.csv` / `edges.csv` | 绘图输入 | 逐节点/逐边清单（stage 用 required_stages 标准标记） |
| `preview-insert-width.png` | 物理宽度预览 | 1600px 宽插入观感目检 |
| `self-check.md` | 自查 | v7，与本版一致 |
| `audit.json` | 机检清单 | figure-auto-review-v1，哈希按最终字节重算 |
| `*.modern.*` | 美化变体 | 不进入本轮验收 |

## 图注（要点，全文见 caption.md）

上层 v4 统一入口（unified.py@a0537aeb）：结构识别 → 六类候选构造（覆盖/依赖检查在各构造器内；可选候选失败跳过、必需 bounded 失败终止）→ plan_bytes 输出字节 SHA-256 去重 →（单候选直接选定｜多候选固定 E1 在线选优）→ 官方方案文件（严格仅 node_to_subgraph、core_schedules 两字段）；诊断记录 --diagnostics 自留不提交。下层冻结官方评估器：边界 COPY 重建 → Step1/2/3 → 多核事件模拟 → Makespan（cycles）与额外 DDR（B）。E1（在线，计入求解计时）与 E0（独立复评）分开表示。提交者仅决定切图、分核、每核 Task 顺序三项。

## 已通过的检查（v7，本轮重导出后目检）

- f3 不穿"六类候选构造"标题；下层标题与节点框无接触；f6b 绕诊断框外缘、诊断文字完整可读。
- 1600px 插入宽度预览逐项目检：无穿字、无遮挡、无裁切、无缺字。
- validate.py 0 error；标准 XML 解析通过。
- 验收标准三项（三决策齐全、E1/E0 分开、研究模块不入主线）维持通过。

## 待对方/整稿处理

- 无阻塞项。若整稿侧对字体字号或配色有统一要求，按统一规范重导。
