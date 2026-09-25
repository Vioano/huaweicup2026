# 来源目录与读取范围

此目录保存索引和哈希，不重复拷贝大型原件。固定Git链接可以直接查看未合并作者分支；本地未跟踪PDF仍在用户原位置，其他队员机器可能没有，不能把下面的路径当作已随PR共享。

## 已继承的章节

| 工作副本 | 原作者入口 | 固定提交 | 本轮处理 |
|---|---|---|---|
| [P1](../../paper/chapters/04-problem-1.md) | [原文](https://github.com/huaweibei123/huaweicup2026/blob/67c0f603960fddf86416d23ca3e85e53561c3c3a/paper/sections/P1-%E9%97%AE%E9%A2%98%E4%B8%80%E8%AE%BA%E6%96%87%E5%88%9D%E7%A8%BF.md) | `67c0f603960fddf86416d23ca3e85e53561c3c3a` | 保留正文，仅固定相对证据链接、增编辑状态头 |
| [P2](../../paper/chapters/05-problem-2.md) | [原文](https://github.com/huaweibei123/huaweicup2026/blob/4591699737ec4fd124f8dc3d3ce2116e0a2387a2/paper/sections/a-q2.md) | `4591699737ec4fd124f8dc3d3ce2116e0a2387a2` | 保留正文，仅固定相对证据链接、增编辑状态头 |
| [P3](../../paper/chapters/06-problem-3.md) | [原文](https://github.com/huaweibei123/huaweicup2026/blob/987fc1aeeabf31cc1b7cb2c19b4fcb81aadc5f96/paper/sections/a-q3.md) | `987fc1aeeabf31cc1b7cb2c19b4fcb81aadc5f96` | 保留正文，仅固定相对证据链接、增编辑状态头 |

每份原稿SHA-256、导入正文SHA-256及逐链接变换都在 [manifest.json](manifest.json)。原稿含未完成图占位、旧时间点研究状态；不因导入就成为最终稿。原稿所属PR也不由本任务代为合并。

## PDF材料

| 相对原仓库路径 | 页数 | 实际阅读范围 | 共享状态 |
|---|---|---|---|
| `docs/HuaweiCup_A_Paper_Writing_Alignment_Bocchi_Style.pdf` | 9 | 全部9页渲染查看；纯图像PDF，文本提取无正文 | 用户本地原件，本PR未上传 |
| `data/raw/a/problem.pdf` | 14 | 结合OFFICIAL_OBJECTIVES核对；正文第5/6页与脚注另渲染查看 | 主库原件 |
| `2025A题优秀论文/A题-面向 Davinci 架构的 NPU 核内调度算法研究.pdf` | 77 | 摘要/目录与结构页；未全文科学审查 | 用户本地原件，本PR未上传 |
| `2025A题优秀论文/A题-2-通用神经网络处理器下的核内调度问题.pdf` | 98 | 摘要/目录与结构页；未全文科学审查 | 用户本地原件，本PR未上传 |
| `2025A题优秀论文/A题-1-通用神经网络处理器下的核内调度问题.pdf` | 59 | 摘要/目录与结构页；未全文科学审查 | 用户本地原件，本PR未上传 |
| `2025A题优秀论文/A题-NPU 核内调度算法设计与优化研究.pdf` | 120 | 摘要/目录与结构页；未全文科学审查 | 用户本地原件，本PR未上传 |

对齐PDF提供编辑方向；四篇2025A材料提供结构参考。它们不替代当前题面，也不证明本队方法的新颖性。获奖身份未核查。为避免不必要传播，本次不上传用户本地PDF；读取哈希用于以后核对同一版本。

## 固定材料导航

- [objectives](https://github.com/huaweibei123/huaweicup2026/blob/e82c20098eb53cfb00d5f2287173f6894b3fb291/docs/a/OFFICIAL_OBJECTIVES.md)：`docs/a/OFFICIAL_OBJECTIVES.md`。
- [p1-full](https://github.com/huaweibei123/huaweicup2026/blob/a1bb4451cd85c46b32bb928d57c81e22cfeca1a6/results/a/p1-branch-refine-full500-20260925/README.md)：`results/a/p1-branch-refine-full500-20260925/README.md`。
- [p2-full](https://github.com/huaweibei123/huaweicup2026/blob/00d311ed0eea0fd86f9840df406956041a7c192a/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md)：`results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md`。
- [p3-full](https://github.com/huaweibei123/huaweicup2026/blob/e70e74e53133856865f4c490cfdb28709a7f1795/results/a/q3-nikolastarx/forest-full500-feedback-20260925/README.md)：`results/a/q3-nikolastarx/forest-full500-feedback-20260925/README.md`。
- [p3-pair](https://github.com/huaweibei123/huaweicup2026/blob/e70e74e53133856865f4c490cfdb28709a7f1795/results/a/q3-nikolastarx/forest-cachepair-delta-20260925/REPORT.md)：`results/a/q3-nikolastarx/forest-cachepair-delta-20260925/REPORT.md`。
- [p1-r7](https://github.com/huaweibei123/huaweicup2026/blob/1b1e439c0eb056a7e1567de0d72a6a987684e645/results/a/p1-r7-construction-probe-20260926/RUN_RESULT_044_K5.md)：`results/a/p1-r7-construction-probe-20260926/RUN_RESULT_044_K5.md`。
- [p2-c04](https://github.com/huaweibei123/huaweicup2026/blob/00d311ed0eea0fd86f9840df406956041a7c192a/results/a/q2-nikolastarx/c04-six-e0-20260926/README.md)：`results/a/q2-nikolastarx/c04-six-e0-20260926/README.md`。
- [p3-final](https://github.com/huaweibei123/huaweicup2026/blob/8416300c7245925795aaa3acc64d4d5b31fa13d5/paper/notes/p3-final-round-method-handoff-20260926.md)：`paper/notes/p3-final-round-method-handoff-20260926.md`。
- [coherent-index](https://github.com/huaweibei123/huaweicup2026/blob/e82c20098eb53cfb00d5f2287173f6894b3fb291/docs/a/research/20260924-coherent-pro/README.md)：`docs/a/research/20260924-coherent-pro/README.md`。
- [control-contract](https://github.com/huaweibei123/huaweicup2026/blob/e82c20098eb53cfb00d5f2287173f6894b3fb291/docs/a/coherent/control-contract-s8ee-20260924/CONTROL_CONTRACT.md)：`docs/a/coherent/control-contract-s8ee-20260924/CONTROL_CONTRACT.md`。
- [theory-final](https://github.com/huaweibei123/huaweicup2026/blob/229b322a9778093782683841f3050db1dbdaabfc/paper/notes/a-theory-coherence-final.md)：`paper/notes/a-theory-coherence-final.md`。
- [figure-plan](https://github.com/huaweibei123/huaweicup2026/blob/697d73c4c6320a75811411912b2f855cacd75d84/paper/notes/A-FIGURE-WORK-PLAN.md)：`paper/notes/A-FIGURE-WORK-PLAN.md`。

聊天入口见 [chat-entrypoints.json](chat-entrypoints.json)，专项范围与已知缺件见 [交接单](../planning/WEB_CLIP_HANDOFF.md)。图/脚本和18组任务见 [图件盘点](../planning/FIGURES.md)。所有“完整/待核”表述以各自范围为准。

## 本轮检查边界

执行 `python3 paper/sources/verify_sources.py` 可在已取得相应Git对象的仓库中只读复查原稿字节、导入一致性、固定对象及新增Markdown文件链接。脚本不联网、不fetch、不运行论文或附件代码。缺少未合并分支对象时会报告缺件，不能因此断言远端原件不存在。

检查结果与未验证项见 [VALIDATION.md](VALIDATION.md)。科学审计、绘图重生成、Web Clip网页全量核验、外部文献核验、LaTeX编译均未由本次检查代替。

## P3最终归档补记

固定提交 `8416300c7245925795aaa3acc64d4d5b31fa13d5` 的[最终报告](https://github.com/huaweibei123/huaweicup2026/blob/8416300c7245925795aaa3acc64d4d5b31fa13d5/results/a/q3-nikolastarx/r9f-final-full500-20260926/FINAL_REPORT.md)、CSV、summary、决策表、图元数据/脚本/三种导出已补入manifest；[本次只读检查收据](p3-final-update-validation.json)记录范围。作者的500份原计划字节审计不冒充整稿者再次独立复核。Forest仍为主算法，R9F作为选择政策的负结果；新增图不自动完成全部正式图需求。
