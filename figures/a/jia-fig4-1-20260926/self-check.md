# 图 4-1 自查记录（甲，v3 返工版，2026-09-26）

对照工作台 Agent 验收意见（#14 评论 5837226124 与 5837354904，针对上一包 be49466c1）逐项处理。说明：本轮验收方为工作台 Agent，乙 lyx 未参与交叉复核；此前自查写"对照乙返工意见"属署名不准确，特此更正。

## 本轮退回项逐条（5837354904）

1. **CSV 逗号引号** → 已修：nodes.csv / edges.csv 改用 Python `csv.writer`（QUOTE_MINIMAL）规范写出，e1 行 note 中的 `(Makespan, scheduled COPY bytes)` 整字段自动加双引号；逐行校验 4 列（nodes）/3 列（edges）无多余字段，机检可正常解析。
2. **required_stages 单值化** → 已修：stage 列不再出现分号合并值。partition / assignment / task_order / node_to_subgraph / core_schedules 各以单独 stage、唯一表 ID 登记为语义子项行（semantic-partition、semantic-assignment、semantic-task_order、semantic-plan-n2s、semantic-plan-cs、semantic-read-n2s、semantic-read-cs），note 写明映射到的图容器/字段与 XML ID（candBox、c1..c6、plan、read）；这是对已有图容器与源码决策字段的证据补录，未虚构算法步骤、未新增图节点。
3. **别名统一** → 已修：nodes.csv / edges.csv 的 id 统一改为 drawio XML ID（cand_box→candBox，c1_bounded→c1，c2_heavy_or_sink→c2 等），edges 端点（identify→candBox、candBox→dedup）随之更新；逐边校验端点全部存在于节点表，不再存在"字面一一对应却无映射"的问题。
4. **候选大框头部遮挡** → 已修：框头缩短为两行（"六类结构候选构造（统一入口 generate_candidates，至多 6 个不同方案）"＋"可选候选构造失败跳过；必需 bounded 候选失败则终止求解"），第一排候选框（c1/c2）上方留白充足，PNG 目检无重叠；strict-private-chain-check 等源码细节移至图内底部 note3 与 DELIVERY 对应表。
5. **构造失败语义** → 已修：固定 `unified.py add`：required=True 时直接 raise，bounded 为必需候选。图面框头、note3、caption.md、DELIVERY.md 统一改为"可选候选失败跳过；必需 bounded 候选失败则终止求解"，不再把求解失败画成仍正常输出。
6. **官方方案→read 虚线穿 diag 正文** → 已修：诊断框右移（XML ID diag，x=480），该虚线加折线（y=836 水平段）沿诊断框外侧走线至 read 顶部；PNG 目检两条输出（方案文件实线 / 诊断 JSON 虚线）独立可辨，无穿框。
7. **audit.sources 初稿路径** → 已修：`paper/sections/P1-问题一论文初稿.md` 为实际仓库路径，章节定位（4.1、4.4.1~4.4.4）移至 note 字段；哈希与固定提交不变（67c0f603…）。
8. **self-check 署名** → 已修：见本文件开头更正说明。
9. **插入宽度** → 见下节。

## 插入宽度检查（新增）

- 版面依据：`paper/template-2025/gmcmthesis.cls` 第 134 行 `\geometry{left=31.7mm,right=31.7mm,...}`，A4 纸宽 210 mm → `\textwidth` = 146.6 mm。
- 等效预览：`fig4-1-preview-insert-146mm.png`，1734×1799 px（≈146.6 mm @300dpi，SVG 内容边界 1163×1203 px）。
- 目检结论：该宽度下标题与各框题可辨认；**正文小字（最小 11 px）物理高度 ≈ 3.9 pt，低于 5 pt 舒适阅读线**，长句（如 note3、E1 框第 3–4 行）在纸面需借助放大阅读。全图按 `\textwidth` 插入时高约 151.7 mm，单栏可容纳。
- 建议：论文正式插入时优先考虑旋转 90° 占页（有效宽约 242 mm，最小文字约 6.4 pt），或在本图获得图面验收后出一版字号放大的论文专用变体。本项如实记录，不声称纸面可读性完全达标。

## 上一轮遗留复核（5837226124，本版状态）

- audit.files 不含 audit.json 自身：v2 已改，本版保持（共 9 项随包文件，见 audit.json）。
- caption/self-check/DELIVERY 哈希：本版在全部文字编辑完成后统一重新计算登记（见 audit.json files），无旧版哈希残留。
- 统计口径：nodes.csv 29 行 = 22 个图节点（id 与 XML ID 一一对应）+ 7 个语义子项行（非独立图节点，note 注明映射）；edges.csv 16 条，与图中实际连线一一对应。

## 常规项

- 三项决策齐全、E1/E0 分开、研究模块未混入：本版图面继续满足。
- 工具：draw.io CLI 导出（`"F:/draw.io/draw.io.exe" --disable-gpu --no-sandbox -x -f svg/-f png -s 2/-f png -s 1.49`）；XML `xml.dom.minidom` 解析通过。
- 版面：PNG（scale=2，2327×2414）目检——分支标签清晰、无文字被线条遮挡、无裁切；候选框头两行与第一排候选框不重叠；plan→read 虚线走诊断框外侧。
- 未完成项：插入宽度下正文小字约 3.9 pt 偏小（见上节），处理方式待工作台/用户定夺（旋转占页或放大字号变体）；其余无。
