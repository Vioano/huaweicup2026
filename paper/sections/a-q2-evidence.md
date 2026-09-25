# P2 章节证据、图件占位与修订记录

本文是 [P2 章节初稿](a-q2.md) 的编辑伴随材料，不作为正式论文正文。作者会话为 `yuanzhifang30-sudo/s-eb28fa11a5664fdfbdd29b3d6e38ca24`，日期 2026-09-25。用户已明确将任务调整为持续跟进算法并写 P2；此前“P1”字样是用户已纠正的笔误。

## 当前稿件采用范围

| 对象 | 固定版本/身份 | 本稿的采用方式 |
| --- | --- | --- |
| 主方法 | `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` | 结构初解 + gap + hypergap，最多三个不同完整计划的原生 E2 评分 |
| 主结果发布 | `1c00079aadbd071de62db17686d5ba3fed1da0f2` | 完整 100×1–5 核，500 次独立 E0；并非本会话重新运行 |
| 最新已读算法资料 | `e4f7b13e4af04914a1264a650831a3959f14a373`，包含 `9404635dea70aa532894506c21d383f22ea6ca81` | 有限 job DP、准备剖析及模板收益上限列入 5.7，不替换主表 |
| 成员 tensor/gap/F1 数据 | 读取提交 `178a3673bd238b20772211427b8134b6db35f5af` 的冻结 CSV | 各自独立固定算法的对照；F1 只列五核完整均值 |
| R5 保存方案静态诊断 | 源码 `1acc50a7f8290fd98fa94a12113281728705d7ca`；本次归档完成结果 | 100 对、200 个条件下界、0 新评分，仅用于研究边界 |
| 外部截图成绩 | 身份与未四舍五入数值未核实 | 不作论文正式同行基线，不写“已超越外部最优” |
| 未提交 tensor_incumbent 实验模块 | 仅有合成检查，未接入、未测真实图 | 不纳入章节主算法或任何结果行 |

主方法是“当前已有完整验证证据的主线”，不是声称它已被队长冻结为最终提交算法。本会话已通过 [Issue 33 的论文范围通知](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5826333267) 联系 P2 队长与协调者，请其给新固定版与采用范围；通知已发出不等于对方已读或验收。正式 TeX 单写归属不变。

随后实际读到队长 [Issue 33 #5826526478](https://github.com/huaweibei123/huaweicup2026/issues/33#issuecomment-5826526478) 的定向证据更新：完整成绩仍为 c665，新增 e4f7b13 没有新正式成绩。已读取所给三个 README 的原文并修订 5.7；这是已读材料回执，仍不是章节验收。队长 Pro r06 正在生成，本会话不重复提问或打断。

## 结构参考与正文组织

用户提供的《论文结构参考.pdf》共 52 页，SHA-256 为 `f302a6d59b7cea9bcfe3c12287a0d6fb76d1dc5d1a0394f88896121c3336fe12`。已提取完整文本，实际重点阅读目录与相关章节的第 2–7、20、26、27、29、30、51 页，视觉查看目录第 4–5 页及问题二起始第 20 页。本稿借鉴其章节组织、模型—求解—结果关系及图表位置，不沿用该文不同赛题的模型、数据、结论或公式。

正文采用 5.1 问题分析、5.2 数据与符号、5.3 模型、5.4 算法、5.5 容量与下界、5.6 结果、5.7 最新探索、5.8 评价与跨问衔接。总摘要、总技术路线与全篇符号表由队长整合时去重；本章的第 5 章及图表编号均可统一调整。

## 资料索引

以下是研发证据索引，不冒充正式发表的外部学术文献。排版前应按全篇规则将实际引用的官方材料和算法文献统一编入参考文献；未查证的论文条目不补造。

<a id="s1"></a>

### S1：原题、固定配置及 P2 执行语义

- [官方目标核验](../../docs/a/OFFICIAL_OBJECTIVES.md)：原题、页码、5～10 分钟口径、平均加速比与额外 DDR 定义。
- [冻结 P2 官方源码](https://github.com/huaweibei123/huaweicup2026/blob/45f647b395b84e9569f418fd33d62c2b8eb4d190/data/raw/a/official/code/multicore_cut_evaluate_problem_2.py)：Task 重建、COPY 多重集、释放条件、Step2/3 与公平共享事件模拟。
- [固定配置](https://github.com/huaweibei123/huaweicup2026/blob/45f647b395b84e9569f418fd33d62c2b8eb4d190/data/raw/a/official/data/config.txt)，SHA-256 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。
- [P1/P2 交接及边界](../../docs/a/Q2_HANDOFF.md)。P1 的 Task 等待和 P1Evaluator 不能直接移植为 P2。

<a id="s2"></a>

### S2：全局下界与固定 FIFO 下界

- [OPTIMALITY_BOUNDS.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/OPTIMALITY_BOUNDS.md)：逐 Pipe 工作、不可分割性、实际计算路径、head/tail 窗口及 COPY 收缩反例，支持式（5-14）至（5-17）。
- [FIFO_BOUND.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/FIFO_BOUND.md)：同核同 Pipe 的实际计算顺序及固定候选的适用域。不得与全局界混用。

<a id="s3"></a>

### S3：主算法及准确的基础字节目标

同一固定提交 `c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f` 下已读：

- [adaptive_hypergap_guarded.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/adaptive_hypergap_guarded.py)：最多三次完整计划评分；字节下降只决定是否追加 hypergap，不剪掉原 gap。
- [hypergraph_cost.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/hypergraph_cost.py)、[binary_hypercut.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/binary_hypercut.py)：物理域、连通度费用、最小割及逐次锚定。
- [gap_candidate.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_candidate.py)、[gap_hyperrefine.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_hyperrefine.py)、[gap_retime.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/gap_retime.py)：链与汇合、16 链区域、固定分核重排。
- [adaptive_guarded.py](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/src/q2_nikolastarx/adaptive_guarded.py)：实际 E2 进程、源/二进制核对、在线开销和失败账本。旧构造器退回初始方案不自动构成一次成功质量验收；完整批次的状态由独立运行收据限定。

成员 gap 适配来源为 P3 会话固定 `a37eb931a22fb7df7e0d00d193538ce5289ae045` 的日历及放置思路；队长 gap 源码保留了从成员 `71616ac7` 适配的来源注释。正文按团队共同成果表述，不将跨会话复用改称本人独立发明。

<a id="s4"></a>

### S4：结构初解与活跃核心

固定 c665 下的 [ADAPTIVE_SEMANTIC.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/ADAPTIVE_SEMANTIC.md)、[ACTIVE_CORE_WAVE.md](https://github.com/huaweibei123/huaweicup2026/blob/c66559a6f8a31ef7b4720e1f7c3c28d61f8dff3f/docs/a/q2-nikolastarx/ACTIVE_CORE_WAVE.md)，结合 `adaptive_budget.py`、`adaptive_semantic.py` 和 `adaptive_frontier.py` 源码阅读。当前 budget 调用明确关闭仅由分量计算不均触发的拆分，不能照搬旧 frontier 文档的默认路线。

<a id="s5"></a>

### S5：容量条件

- [P2 容量与 DDR 冻结源码审计](../../docs/a/q2/PRO_CAPACITY_AUDIT_20260925.md)：区分实际 Step2 完整物理序列、零 spill 正常返回、Step3/全局成功，以及理想时间模型与机器实现。
- [F1 方法](../../docs/a/q2/feedback/FRONTIER_GAP.md)、[审阅](../../docs/a/q2/feedback/FRONTIER_GAP_REVIEW.md)，源码 `4a501d7f4a8b780263e097a963e12dcb66178e69`。
- 命题 2 使用真实完整本地序列的闭区间条件；F1/R4 的保守替代模型各有更窄守卫，不能隐去区别。

<a id="s6"></a>

### S6：完整主结果及本次表格重算

- [完整 500 格结果说明](https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/RESULTS.md)、[审计 report.json](https://github.com/huaweibei123/huaweicup2026/blob/1c00079aadbd071de62db17686d5ba3fed1da0f2/results/a/q2-nikolastarx/hypergap-full500-audit-20260925/report.json)。求解器 c665，runner `ff47cbca4a953602dec7e4b959bbb10a016eca9a`。
- [本文表格重算脚本](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/build_snapshot.py) 与 [evidence.json](../../results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/evidence.json)。脚本从固定 Git 对象读取 CSV/报告，核对 500 个唯一坐标、各图分母、实际图/config 哈希、终态，重算均值、DDR/spill、配对数及耗时分位数。
- 复算入口：仓库根目录执行 `python -B results/a/q2-yuanzhifang/feedback-20260924/paper-draft-20260925/build_snapshot.py`。要求相应固定提交可读取及只读官方数据已解出。不构造方案、不调用评分。
- 本次复算通过；生成证据 SHA-256 `c9656605c5d47e99f260fd63d62f3fe41bc83137e7b03ed741808e0a9a64b5a7`。不再次声称本会话核对了队长全部原始压缩结果与运行收据；原作者的完整审计与本次汇总复核是两层证据。
- 下界内 5% 的计数取已发布下界审计。本文重新核对了报告口径，没有重新运行其全图下界扫描。

<a id="s7"></a>

### S7：成员对照与负结果

- [tensor 500 格](../../results/a/q2-yuanzhifang/feedback-20260924/full-coverage/all500/README.md)，算法 `e64723bdf99669c44f76d8e90ab0379a8578522e`；[gap 500 格](../../results/a/q2-yuanzhifang/feedback-20260924/full-coverage/gap-full500/README.md)，算法 `384b6c2a7ff937ca44180dee09a9d4bcaea0c50d`。
- [F1 五核 100 图](../../results/a/q2-yuanzhifang/feedback-20260924/full-coverage/frontier-k5-100/README.md)，105 个总测量坐标含另 5 个三核格；不能写成 500 格。
- [020/045 保存计划的静态机制](../../docs/a/q2/feedback/COMPONENT_DDR_STATIC.md)。它们是五核开发案例，使用既有 E0，非新增得分。
- tensor 与 gap 各有 501 次 solver、500 次 E0 的实际成本，包含已记录的故障/限时成本；F1 为 105 solver/105 E0。跨时段与硬件不可直接计算稳定端到端提速。

<a id="s8"></a>

### S8：COPY 事件与容量安全重排

固定 `e6925b5747b4e2dcccf2eb4a5ff41ea3f33502d8` 下的 [COPY_EVENT_GUARDED.md](https://github.com/huaweibei123/huaweicup2026/blob/e6925b5747b4e2dcccf2eb4a5ff41ea3f33502d8/docs/a/q2-nikolastarx/COPY_EVENT_GUARDED.md) 与 [CAPACITY_SAFE_RETIME.md](https://github.com/huaweibei123/huaweicup2026/blob/e6925b5747b4e2dcccf2eb4a5ff41ea3f33502d8/docs/a/q2-nikolastarx/CAPACITY_SAFE_RETIME.md)。015 的 40701 是作者已发布单次官方 E0 结果；本会话读到报告，未再次运行。它不是 c665 full500 的新数值，也不是新的统一 500 格均值。

<a id="s9"></a>

### S9：最新有限作业流水 DP

固定 `9404635dea70aa532894506c21d383f22ea6ca81` 的 [TEMPLATE_FINITE_JOB_PIPELINE.md](https://github.com/huaweibei123/huaweicup2026/blob/9404635dea70aa532894506c21d383f22ea6ca81/docs/a/q2-nikolastarx/TEMPLATE_FINITE_JOB_PIPELINE.md)，以及同提交的 `TEMPLATE_CAPACITY_PIPELINE.md`。本稿实际读取完整方法说明及新增差异。DP 的四项合成测试属于作者报告，不写成本会话执行；本次没有新真实图构造/E0/E2。

式（5-20）是固定标量阶段系统的等式，非官方周期定理。最新实现的状态标签剪枝还需保留字典序相等条件；完整复杂度、256 模板位置上限与 2000000 次可行转移预算见原说明。若后续将其升级为主算法，需要重新确认构造源、实际 runner、真实图覆盖及官方结果。

<a id="s10"></a>

### S10：R4/R5 条件界诊断与 Pro 来源

- [R4 方法](../../docs/a/q2/feedback/COMPONENT_GATE_R4.md)，未进行真实冷求解与独立 E0；冻结三例提案不能当作已运行。
- [R5 适用域](../../docs/a/q2/feedback/IDEAL_BOUNDS_R5.md)、[100 对静态结果](../../results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/report.json)、[完成回执](../../results/a/q2-yuanzhifang/feedback-20260924/ideal-bound-r5-static/completed-receipt.json)。结果 SHA-256 `53d102dbe6ce461cae05f110cee01cb6949c45370b283e91dcd4492fded4db0a`。
- 完成窗口 2026-09-25 03:31:13.9620654Z 至 03:32:57.0028234Z，exit 0。程序内静态诊断耗时 102.5018218999976 s，不是 solver 端到端时间。R4 与 R5 均触发 020/022/029/044/045/057，新增触发为零，0 新评分。
- 第一窗口 RAM 不足、0 启动的收据仍保留，不能覆盖为成功记录。第二窗口完成结果是新增事实，本稿据此更正旧段落的“尚无 report”。
- Pro 三轮公开原件位于 `AI chats/P2-capacity-ddr-6ab57979/`，最新快照 `snapshot-20260924T215321Z.md`。公开建议经过冻结源码复核后才转成文中限定命题；Pro 自报微型实验、未取得附件及未闭合机器误差引理不当成本机实验或正式证书。

<a id="s11"></a>

### S11：队长新发的准备剖析、模板上限及恢复计划

以下均实际读取固定 `e4f7b13e4af04914a1264a650831a3959f14a373`：

- [preparation-profile README](https://github.com/huaweibei123/huaweicup2026/blob/e4f7b13e4af04914a1264a650831a3959f14a373/results/a/q2-nikolastarx/preparation-profile-20260925/README.md)：014/K1 保存计划，Linux 单次 preparation-only，0 E0/native、0 重试；52.521 s 的 profiler 准备中 list.index 自身时间 24.301 s。这不是新求解器成绩或替代实现提速。
- [template-opportunity README](https://github.com/huaweibei123/huaweicup2026/blob/e4f7b13e4af04914a1264a650831a3959f14a373/results/a/q2-nikolastarx/template-opportunity-20260925/README.md)：九图识别域、其余输出不变条件下的五核均值贡献上限 +0.155990，不是可达预测、留出测试或新均值。
- [pro-r05-recovered README](https://github.com/huaweibei123/huaweicup2026/blob/e4f7b13e4af04914a1264a650831a3959f14a373/results/a/q2-nikolastarx/pro-r05-recovered-20260925/README.md)：按保存 owner/start 和原始 witness 恢复 003/K2 被代理拒绝的原始计划，基础 COPY 为 5207554 B。官方 Makespan 尚无测量，因此不能把静态代理 230838→241374 的拒绝当成官方退化；本文未把该计划列入正负实测例。

本会话读取上述原报告，未重复 profiler、算法、评分或逐字节恢复验证。准备层语义保持优化属于基础设施会话，不由论文写作会话并行修改共享 evaluator。

## 图件与最终补证清单

| 图号 | 本次状态 | 最终输入与检查 |
| --- | --- | --- |
| 5-1 | 文字占位 | 最终主程序调用关系；尚未接入的模块不能画进执行主线 |
| 5-2 | 文字占位 | 手算合成例或完整实际物理序列；区分静态容量与运行峰值 |
| 5-3 | 文字占位 | 固定版本 100×5 逐格结果、固定分母；缺测不连线 |
| 5-4 | 文字占位 | 同图同核同配置的固定 plan/trace；正负案例均保留 |
| 5-5 | 文字占位 | 同硬件同并发的完整求解墙钟及质量，不混内核时间 |
| 5-6 | 文字占位 | 有适用域的全局界证书；与固定 FIFO 界分离 |

正式制图时使用项目 `scientific-figures`/`scientific-figure-making` 规范与标准绘图工具，保留数据、脚本、矢量输出和视觉验收。本轮没有生成看似真实的模拟成绩图；用户允许文字占位，故优先把指标与证据要求写清楚。

同主程序消融、同硬件质量—耗时实验、最终版本完整覆盖和全篇文献/符号合并仍是待补证，不据此自行启动新的批次。共享正式 TeX 由队长整合，本会话持续修订本 Markdown。

## 更新规则与本轮验证

新方法出现后，先核对固定提交、适用条件与复杂度，更新 5.7；只有与该实现绑定的新结果才更新对应实验。替换主方法时同步重写 5.4、伪码、预算、表格与图源，不保留过期算法叙述配新成绩。评分缺口仍按缺口表示，算法开发者的报告、汇总重算、独立复评和最终验收分开记录。

本轮只读查阅官方语义、算法固定源码/说明、冻结结果并重算论文表；没有新 solver/Step2/Step3/E0/E1/E2，也没有重启 Pro 或后台实验。算法临时代码保留在原工作树，不随论文提交伪装成已验证主方法。

交付检查：表格重算脚本通过；本地文档链接及 11 个资料锚点、20 个连续编号公式、8 节标题、6 个图占位检查通过；示例 007/020/045 的五核数字再次与冻结 CSV 核对。Markdown 解析后的 6 张表（含符号表）列数一致，已视觉查看正文开头及主结果表；预览保留 TeX 文本，不称作最终数学排版验收。Git 空白检查、文件编码、个人路径及凭据模式检查通过。Windows 无 dot_clean，已对本次 paper/结果具体目录做只读元数据扫描，无 `._*`、`.DS_Store` 或 `__MACOSX` 项；未作跨目录清理。
