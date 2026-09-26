# 图 4-1 自查记录（甲，v5，2026-09-26）

## 本版（v5）依据
- 实际论文模板：paper/template-2026/gmcm2026.cls（origin/main@e82c20098eb53cfb00d5f2287173f6894b3fb291），geometry：A4，top=30mm bottom=18.5mm left=right=22.5mm，正文宽 165mm、正文高 248.5mm。template-2025 仅为仓库内旧模板，非当前口径。
- 实际导出边界：SVG viewBox 703x689（draw.io CLI 导出）。按 165mm 宽插入，高 161.7mm，正文页内可容纳。
- 字号换算：最小 10px 约 6.65pt；主标签 11-12px 约 7.3-8.0pt（工作台建议的约 8pt 目标按主标签达到，未自设硬门槛）。
- 生成命令：见 audit.json.command（draw.io desktop CLI --disable-gpu --no-sandbox；validate.py 0 error）。

## 历史稿区分
- v1=879c3dc3（首版，1163x1203、146.6mm 口径）；补件=01425aa3；v3=ddd9c242；夜班第6/7版=be49466c1/a2502108；v4=c44e4d40（重排 703x689，但 audit 哈希未随最终编辑重算、self-check 仍为 v3 内容，本版已修正）。
- 本版 v5：仅打包一致性修正（audit 哈希按最终字节重算、self-check/DELIVERY 更新至本版、audit.files 移除旧 fig4-1-preview-insert-146mm.png 并登记新 preview-insert-width.png），图面 XML 与 v4 相同未改。

## 检查结论（v5）
- 插入宽度预览 preview-insert-width.png（1600px）目检：无穿字、无遮挡、无裁切。
- 验收标准三项（三决策齐全、E1/E0 分开、研究模块不入主线）维持通过。
