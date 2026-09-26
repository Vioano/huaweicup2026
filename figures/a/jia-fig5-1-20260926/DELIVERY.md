# 图 5-1 交付包｜P2 张量通信优化技术路线（v4）

- 图号：5-1　版本：v4（2026-09-26，按 F51-R06 收尾意见（#14 评论 5844708118）修订；v1=3992a4e96、v2=e3e8d3627、v3=b17bb0e48 保留于 git 历史）
- 主责：甲（farmeruncle123）　输入数据约束：仅仓库固定提交，无外部数据；0 新实验

## 本版（v3）逐条修订（R01 已关闭不再列）

1. **F51-R02 残项（module 源码对应）**：score.module 改为「guarded_component._score（oracle 由 adaptive_guarded.score_adapter/native_e2 提供）」（主入口 :11 实际 from .guarded_component import _score）；plan.module 改为「adaptive_hypergap_guarded 输出、adaptive_guarded.main 写 plan」，删除 P1 串入的 "unified"；hyper.module 改为「gap_hyperrefine.refine（调用 hypergraph_cost / binary_hypercut）」。
2. **F51-R03 初解调用顺序**：route 改为单个编号大框，严格按 adaptive_semantic.build :43–84 的调用顺序：① 词资源识别成功 → resource_word（立即返回）；② 否则归约树守卫成功 → tree_paired_leaves（立即返回）；③ 否则一般路由：分量数 ≥k → component_route（adaptive_frontier；仅共享外部输入超容量时尝试波次：active_core_wave 式(5-7) 最少核，不支持退 shared_input_wave，波次整体不支持回 component_envelope），分量数 <k → DAG 最早完成；④ 一般方案完成后条件向量修复（vector_lanes 识别且大张量跨核 → vector_arrival）。①② 成功不再流经 ③；br_shared/cores 菱形移除、内容并入 ③ 文字；恢复 resource_word；allow_component_split=False 保留。主图/caption/nodes/edges 四处一致。
3. **F51-R04 构造异常**：note53 异常一项改为「构造意外异常、字节证据非法或评分异常 → 记录 unknown 并退回 Π₀（入口 :27–100）」；保留 UnsupportedStructure 区别（gap 不支持→Π₀；hyper/retime 不支持→保留已有候选）。
4. **F51-R05 视觉**：score/select 间距增至 24px，e13「全部评分有效」不再压 select 首行；e13b 标签改短「异常」置于左缘留白（完整可见，不裁切），详细释义在 note53；s1×s2 纯线交叉维持已记录口径。页面预览重编译：图号「图 5.1」（pdftotext 实测）、TeX 图注改用数学模式（Pi_0 / Pi_gap / Pi_hypergap），pdftotext 无 U+FFFF 方框/缺字；实际图注 4 行（如实记录，不强行压行）；插入宽 148mm、图高 214.8mm，Pages=1、无超页。
5. **F51-R06 命令/算术**：xelatex 命令去掉中文括号说明，补齐真实步骤（git archive 锁定模板完整 commit e82c2009… → 复制 page-preview-main.tex 为 main.tex → 编译 → 拷回 PDF/PNG）；字号算术按审阅公式纠正并如实记录：10px 在 711px 宽、165mm 下约 6.58pt，144mm 下约 5.66pt（v2 误写 5.90，系口径混用，已更正）。

## 文件清单

| 文件 | 角色 | 说明 |
|---|---|---|
| fig5-1-p2-tensor-comm-route.svg/.png/.drawio | 主图 | viewBox 实际 711×1032 |
| fig5-1-page-preview-template2026.pdf/.png + page-preview-main.tex | 真实页面预览 | 148mm 插入 + 图 5.1 图注，单页无超页 |
| nodes.csv / edges.csv | 绘图输入 | 17 节点（id/stage/module/note）/ 19 边 |
| caption.md | 图注 | 页面预览所用版本 |
| preview-insert-width.png | 物理宽度预览 | 1500px |
| self-check.md / audit.json | 记录 | v3 |

## 已通过的检查（v3）

- validate.py 0 error；2 处纯线交叉（s1×s2、e12×s1）无文字/标签压盖，已记录。
- 1500px 插入宽度目检：①②③④ 全部可见无裁切；三类去向+唯一计划路径可唯一读出；边标签不压框内正文。
- pdftotext「图 5.1」、无 U+FFFF、Pages=1、无超页。

## 未完成项

- 无（modern 变体不在本轮）。

## v4 增补（F51-R06 收尾，5844708118）

- **命令块重写**：audit.command 的页面预览段改为审阅方给出的可复制 Git Bash 版本（repo_root 自解析、mkdir -p、tar --force-local——本机 Windows 盘符路径必需、无中文混入可执行行），注释与工具版本移至块外/尾注。
- **本机实际执行**：全链每步退出码 0；pdftotext 实测图号「图 5.1」；最终 PDF/PNG 落在交付目录。
- **插入宽 148→146mm**：148mm 时 Overfull vbox 6.7pt（内容超 2.4mm），降为 146mm（正文宽 88.5%）后 0 警告；图高 212.0mm + 4 行图注 ≤ 正文高 248.5mm。
- **字号记录更正（按审阅公式）**：10px 在 711px 宽、165mm 下 ≈6.58pt；146mm 下 ≈5.83pt（148mm 口径为 5.90pt）。v2 的 5.90 与 v3 的 5.66 均系插入宽度口径不一致，已按实际宽度统一。
- 主图与其余附件字节不变；PDF 因重编译字节更新（705202a2…），PNG 渲染确定性字节不变。
