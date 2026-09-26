# 图 4-1 自查记录（甲，v7，2026-09-26）

## 本版（v7）依据

- 实际论文模板：paper/template-2026/gmcm2026.cls（origin/main@e82c20098eb53cfb00d5f2287173f6894b3fb291），geometry：A4，top=30mm bottom=18.5mm left=right=22.5mm → 正文宽 165mm、正文高 248.5mm。
- 实际导出边界：SVG viewBox 710×689（draw.io CLI 导出）。按 165mm 宽插入 → 高 160.0mm，正文页内容纳。
- 字号换算：最小 10px → 10/710×165/0.3528 ≈ 6.65pt；主标签 11–12px → 7.3–8.0pt（工作台建议约 8pt 目标按主标签达到，未自设硬门槛）。
- 生成命令：见 audit.json.command（draw.io desktop CLI --disable-gpu --no-sandbox；validate.py 0 error）。

## v7 修订核对（逐条对应工作台 #14 评论 5843410014）

1. f3 出口实际改底边（exitX=0.5;exitY=1），折点 y=229 走 candBox 底与 dedup 顶之间空隙；重导出 PNG 目检：不再纵穿"六类候选构造"标题与框内部。
2. 下层标题带：read/copy/steps/sim/出口节点整体下移 16px，layerBottom 加高至 268px；重导出目检：长标题下沿与 steps 顶边（y=430）脱离接触。
3. f6b 改 E1 右中出、经 x=710 绕诊断框右缘下行入方案文件；目检：不穿"--diagnostics"文字，诊断虚线与方案实线可辨。
4. DELIVERY.md 全量重写为 v7（旧 v3 字节作废）；self-check.md 本版正文与真实状态一致；"无穿字"等结论均基于本轮重导出（viewBox 710×689）的 PNG/SVG 目检，非沿用旧说明。

## 检查结论（v7）

- 流程节点/连线与 nodes.csv/edges.csv 一致（identify→candBox→dedup→(single|e1)→plan→read→copy→steps→sim→out1/out2；single→diag 旁支；e0→read 独立复评）。
- 1600px 插入宽度预览（preview-insert-width.png）目检：无穿字、无遮挡、无裁切、无缺字。
- validate.py 0 error；标准 XML 解析通过。
- 验收标准三项：三决策齐全（金色方案文件节点仅 node_to_subgraph/core_schedules）；E1（在线）与 E0（独立复评）分开表示；研究模块未混入 v4 主线。维持通过。

## 历史稿区分

- v1=879c3dc3（首版）；补件=01425aa3；v3=ddd9c242；夜班第6/7版=be49466c1/a2502108；v4=c44e4d40（重排 703×689）；v5=dc13fac2a（打包一致性）；v6=2a03d2972（已撤回）/9749a0963（更正版，标题带首次独立）。
- 本版 v7：图面三处连线/遮挡实际修复（非仅说明）+ 交付记录与真实状态对齐；历次稿均保留于 git 历史，未覆盖。

未完成项：无。
