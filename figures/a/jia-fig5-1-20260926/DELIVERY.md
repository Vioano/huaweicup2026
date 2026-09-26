# 图 5-1 交付包｜P2 张量通信优化技术路线（v2）

- 图号：5-1　版本：v2（2026-09-26，按首轮返工单 F51-R01～R06（#14 评论 5844340834）修订；v1=3992a4e96 保留于 git 历史）
- 主责：甲（farmeruncle123）　输入数据约束：仅仓库固定提交（P2 初稿@615b1a5f、主算法源码@c66559a6），无外部数据；0 新实验

## 本版（v2）逐条修订

1. **F51-R01 来源登记**：audit.sources 全部改为纯仓库路径 + 完整 40 位 commit（paper/sections/a-q2.md、a-q2-evidence.md @615b1a5f7913a97fff8924cfec9936d3d303c6fc；算法源 @c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f），章节说明移入 note；**新增 adaptive_budget.py / adaptive_semantic.py 实际字节**（R03 依赖）。
2. **F51-R02 节点表**：nodes.csv 增加非空 module 列（真实模块/文档依据）；stage 按派发模板：route→structure、gap→gap、hyper→hypergap、retime→fixed_assignment_reorder、dedup→deduplicate、score→full_score、plan→final_plan；其余节点用对应语义 stage；audit.table_columns 同步。表与 drawio 元素一一对应，边端点全部存在。
3. **F51-R03 结构初解/侧栏**：删除通配符"未接入"清单——route 节点按真实调用链标注 tree_frontier→tree_paired_leaves、vector_lanes/vector_arrival、component_envelope/adaptive_frontier（allow_component_split=False）；侧栏 res 改为概括表述"未接入本入口的容量保护/就绪匹配等研究"。活跃核选择改为**共享输入条件分支**（br_shared 菱形：是→cores 式 5-7；否→直接汇合 Π₀）；条件向量修复写入 route 节点文字（"切开大向量张量时 vector_arrival 通路修复（条件分支）"）。已核 adaptive_budget.py:2-20（wave_route/component_route）、adaptive_semantic.py:17-88（tree/vector 调用）。
4. **F51-R04 失败回退**：新增 score→plan 独立分支"异常/未知：记录 unknown 并退回 Π₀"（入口 :85–100 实测：except 分支 return baseline）；成功路径 score→select→plan 仅在"全部评分有效"时走。三类去向（gap 不支持→Π₀；hyper/retime 不支持→保留已有候选；异常→记录并退回 Π₀）在 note53 节点与图注可唯一读出。
5. **F51-R05 实际视觉**：三条问题边标签改短（"是"/"否"）并移入留白走廊，详细条件入 nodes.csv 边注与图注；e12/e13b 交叉消除（换锚点）；s1×s2 存在一处线交叉（无文字压盖，已记录）。**新增真实模板编译页面预览** fig5-1-page-preview-template2026.pdf/.png：template-2026（gmcm2026.cls@e82c2009）XeLaTeX 实编译，插入宽 144mm（正文 87%）、图高 211.2mm + 三行图注 ≈ 228mm ≤ 正文高 248.5mm，编译日志无 "Float too large"、pdfinfo Pages=1、pdftotext 实测图号「图 5.1」；caption.md 精简为页面预览所用版本（详细说明保留 DELIVERY）。
6. **F51-R06 可复现命令**：audit.command 全部为实际执行过的合法命令——路径字符串加引号（Image.open('…')/save('…')），无观察结果混入；执行结果（退出码 0、validate 0 error、输出尺寸）移入 self-check 与 audit.insert_width_check；工具版本在 command 尾注。

## 文件清单

| 文件 | 角色 | 说明 |
|---|---|---|
| fig5-1-p2-tensor-comm-route.svg/.png/.drawio | 主图 | viewBox 实际 732×1074 |
| fig5-1-page-preview-template2026.pdf/.png + page-preview-main.tex | 真实页面预览 | 144mm 插入 + 图 5.1 三行图注，单页无超页 |
| nodes.csv / edges.csv | 绘图输入 | 20 节点（id/stage/module/note）/ 22 边 |
| caption.md | 图注 | 页面预览所用三行版 |
| preview-insert-width.png | 物理宽度预览 | 1500px |
| self-check.md / audit.json | 记录 | v2 |

## 已通过的检查（v2）

- validate.py 0 error（34 warnings：容器/菱形提示；仅剩 s1×s2 一处线交叉，无文字压盖）。
- 1500px 插入宽度目检：边标签不压字、不被裁切、箭头端点明确；三类去向可唯一读出。
- 主图/caption/nodes/edges 三处口径一致；实际调用模块不再声称未接入。
- pdftotext「图 5.1」、Pages=1、无超页。

## 未完成项

- 无（modern 变体不在本轮）。
