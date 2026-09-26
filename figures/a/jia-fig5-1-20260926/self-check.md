# 图 5-1 自查记录（甲，v2，2026-09-26）

## 实际执行结果（F51-R06，本机制图环境）

- 导出命令与退出码：draw.io CLI（--disable-gpu --no-sandbox）SVG/PNG 导出 rc=0，输出 figures/a/jia-fig5-1-20260926/fig5-1-p2-tensor-comm-route.svg（viewBox 732×1074）与 .png（1464×2148, scale=2）。
- validate.py：0 error / 34 warnings（容器包含、菱形提示类；1 处 s1×s2 线交叉为纯连线相交，无文字/标签压盖，已记录）。
- 页面预览：XeLaTeX rc=0，main.pdf 1 页（pdfinfo Pages=1），pdftotext 实测图号「图 5.1」，编译日志 0 处 "Float too large"；pdftoppm -r 110 导出预览 PNG。
- 尺寸：165mm 宽插入高 242.1mm（纯图）；页面预览插入宽 144mm → 图高 211.2mm + 三行图注 + 浮动间距 ≈ 228mm ≤ 248.5mm；最小字 10px→6.39pt@165mm、5.90pt@144mm（fontSize×W/732×72/25.4）。

## F51 逐条自查（对应 5844340834）

1. R01：sources 纯路径+40 位 commit（615b1a5f7913a97fff8924cfec9936d3d303c6fc / c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f）；新增 adaptive_budget.py、adaptive_semantic.py 实际字节哈希。已完成。
2. R02：nodes.csv 加 module 列（全部非空、有真实依据）；7 个必需 stage 全覆盖（structure/gap/hypergap/fixed_assignment_reorder/deduplicate/full_score/final_plan）；audit.table_columns 同步 id/stage/module/note。已完成。
3. R03：删除通配符未接入清单；route 按真实调用链（已核 adaptive_budget.py:2-20、adaptive_semantic.py:17-88）；活跃核选择改为共享输入条件分支（br_shared）；条件向量修复写入 route 文字。主图/caption/nodes/edges 三处一致。已完成。
4. R04：score 增加两条输出——"全部评分有效"→select、"异常/未知：记录 unknown 并退回 Π₀"→plan（入口 :85–100 实测 except 分支 return baseline）；三类去向在 note53 与图注唯一可读。已完成。
5. R05：三条边标签改短移走廊；e12/e13b 交叉消除；新增真实模板编译页面预览（144mm、图 5.1、单页无超页）；caption 精简为三行版。已完成（s1×s2 一处纯线交叉已记录，无文字压盖）。
6. R06：audit.command 改为实际执行过的合法命令（引号路径、无观察结果混入）；结果与尺寸入本文件与 audit.insert_width_check。已完成。

## 验收标准维持

- 分支/候选保留/评分次数与冻结入口一致（保留 v1 已核正确项）。
- 静态通信目标与最终 Makespan 评价分开；未接入研究模块不入主线（res 为概括表述）。
- 历史稿：v1=3992a4e96 保留于 git 历史。

未完成项：无。
