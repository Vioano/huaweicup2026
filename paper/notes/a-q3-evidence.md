# P3 章节证据索引与修订约定

对应正文：[问题三 Markdown 初稿](../sections/a-q3.md)。本文件为合稿与复核记录，不直接作为参赛论文正文。

## 写作范围与衔接

用户已澄清原请求中的“P1”为笔误，本任务整理 P3 完整思路。按用户指定的 `paper/论文结构参考.pdf` 参考章节层次，使用问题分析、模型、算法、结果与局限的结构。参考 PDF 为 52 页的往届评审方案论文，只参考其组织方式；它的统计模型、数据、图、姓名和结论均不是本题成果。PDF SHA-256：`f302a6d59b7cea9bcfe3c12287a0d6fb76d1dc5d1a0394f88896121c3336fe12`。已读取目录、相关 P3 章节文字，并查看物理第 35、40 页图像；不声称逐页审读全 52 页。

本 session：`yuanzhifang30-sudo/s-3d9c78db26714786b88b987ca6f58e2b`。正文及本索引为本 session 单写；正式 TeX 由队长整合。已向队长发送[范围与固定版核对](https://github.com/huaweibei123/huaweicup2026/issues/51#issuecomment-5826374399)。本稿采用 P1/P2 已沟通的 $\phi$、$\kappa$、$\sigma$，但不把 P1 的 Task 完成门控搬入 P2/P3。

写作期间继续读到队长[2026-09-25T04:05Z 的目标更正与新单格通知](https://github.com/huaweibei123/huaweicup2026/issues/51#issuecomment-5826502623)，已实际读取 `a73d1e1e664ef95e6cdc8d9d0da2d95fba7aa718` 的 `OBJECTIVE_AUDIT.md`：Makespan 仍是首要质量量，CacheGain 是同计划相对效益核心比较；当前算法只按 M 接受，尚未将 G 作为接受条件。正文 §6.2.3、§6.7 已据此修订，未改变既有算法或实验预算。

另读取新发布 `e96a8551d6b3c92bbf00285376ce950f9246c0dc` 的前缀 Linux 机制报告及 `62c69b20ab887c76567dbab5fcce6eef30107b5c` 的静态构造说明，加入 §6.4.3、§6.6.3。该项是 044/k5 单格 38390→38024，0 P2、solver wall 未知；只按已发布报告引用，未独立核全部原件，不替换完整主表。完整算法最新可用版本仍为下表所列固定版本。

2026-09-25T04:32Z 后继续跟进到 `28e8c7ddfe2223b2261056f554259c43d5bba272`。新增的是对已保存044/k5结果的 Cache 事件和实际路径分析，0新官方调用，不是新统一算法。本稿在 §6.5.4–6.5.5、§6.6.4 加入固定读取集合的命中上界、取整共享服务研究界及启动竞争分解；主表保持原版本。

## 主算法与数据身份

| 项目 | 固定版本或内容 | 本稿采用方式 |
|---|---|---|
| 完整统一算法 | `311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1`，`src.q3.forest_solve.main` | §6.3 主方法；不是只有 `adaptive_solve` 的旧版 |
| 最终 500 格 feed | `19bebf35205d23fdd832781540f8879da52eeb62`，十份 `board-feed-sNN-revision2.json` | 全部 100 图 × 1–5 核，revision 2，仅补证据不改原成绩 |
| 官方 code 聚合身份 | `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0` | 逐格声明一致；本次写作未重新执行 E0 |
| 配置 SHA-256 | `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9` | L1/UB、带宽、500 周期跨核等待及只读 Cache 固定 |
| 完整结果与配对审计快照 | `cf4d77a018def540358c3b4667c2d2466390981a` 下的两份 `independent-audit.json` | 团队固定审计数据，不假称本会话重跑全部原件 |

完整 feed 目录为 `results/a/q3-nikolastarx/forest-full500-20260925-s59/20260924T2122Z-s59ee/revision2-baseline-draft/`。各输入 Git 原字节 SHA、字节数、核对项与统计记录在[根会话复核结果](../drafts/p3-published-summary-audit.json)。复现命令为：

```powershell
python -B paper/tools/audit_p3_chapter.py
```

脚本只读十份固定 feed 和两份发布审计，不调用 solver、derive、Step、E0/E1/E2，也不下载或展开大 trace。需本地 Git 对象可读；Git 部分克隆若缺对象，获取所需对象的成本与重新评估不同。

本次自行重算并核对：500 格完整覆盖、相同算法 SHA/入口、最高 revision、状态、图/配置/官方身份绑定、计划与配对声明绑定、P3 平均周期、逐图命中率平均、平均额外搬运、求解墙钟统计、声明调用账 500 solver / 973 E0。元数据身份一致不等于重新 hash 每份原始计划和结果。

本次从固定团队审计引用：逐图 $B_i/M_i$ 的平均、同计划 P2/P3 的平均、汇总 hit/miss 字节命中率，以及负收益格的全量清单。原审计说明其核对原件与复用证据的范围；本稿没有重复核全部大体积原件。四个负例的 P3 周期已与本次 feed 对齐。

Luna medium 的第一份[feed 审阅](../drafts/p3-forest500-audit.json)保留独立读取结果及限制。其额外尝试的压缩 Git 对象批量映射未能可靠完成，已停止；不能据此判为源文件缺失或 500 格无效，也不能宣称这次已 hash 600 个 B/P2 原件。随后根会话使用上述限定小文件脚本完成可复现核对。未新增算法实验。

## 逐项来源与可用结论

| 正文部分 | 固定来源 | 可支持结论与限制 |
|---|---|---|
| §6.2 官方目标、输出与计时 | [官方目标核验](https://github.com/huaweibei123/huaweicup2026/blob/2da54f2bcfb85e033df900b03b4d181a698fd012/docs/a/OFFICIAL_OBJECTIVES.md)；冻结 `multicore_cut_evaluate_problem_3.py`、`config.txt` | Makespan 与求解墙钟分开；P3 Cache 字节口径；配置不能改 |
| §6.3 路由与接受策略 | [forest_solve](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/forest_solve.py)，同提交 witness/pipeline/calendar/expanded/adaptive 及 guarded 模块 | 新基准、固定结构候选、总在线 E0 ≤ 3、仅严格 M 改进接受 |
| §6.3.1 一般 DAG 日历 | [gap_dag.py](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/gap_dag.py)，同提交 `gap_calendar.py`/`GENERAL_GAP.md` | 凝聚链、固定就绪秩、至多两链联合归核、持久 AVL；复杂度不含输入展开与官方评价 |
| §6.3.2 连续划分 | [shared_pipeline.py](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/shared_pipeline.py) | 精确解固定串行阶段最小最大段和；不等于原题最优 |
| §6.3.3 森林交换证明 | [FOREST_FRONTIER_ORDER.md](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/docs/a/q3/FOREST_FRONTIER_ORDER.md)，同提交 `forest_memory_order.py` | 固定树、子树不交错、内部输出标量峰值；不覆盖真实 Cache/双池/跨流水线 |
| §6.3.4 条件下界 | [pipe_bound.py](https://github.com/huaweibei123/huaweicup2026/blob/311322b996c0948e8a6a9c7ec6ddfe6ae41fbee1/src/q3/pipe_bound.py) | 单节点子图、整数 M/V、已证明原依赖与 FIFO；不支持 COPY 收缩歧义；不证明合法执行 |
| §6.4、§6.6.3 容量流水 | [固定单例报告](https://github.com/huaweibei123/huaweicup2026/blob/7edacdd97a7be36a402af20bc8bfa8a7454dbbe0/results/a/q3-yuanzhifang/pipeline-capacity-20260925/REPORT.md)；源码 `2df4a5fa70d7a59492a7477e9ecd706501e64ad6` | 044/k4 实测 40927→37581、extra DDR 135168→121088 B；非全家族或统一500格结论 |
| §6.4.3 完整 Task 前缀 | [固定静态说明](https://github.com/huaweibei123/huaweicup2026/blob/62c69b20ab887c76567dbab5fcce6eef30107b5c/results/a/q3-nikolastarx/pipeline-prefix-static-20260925/README.md)；[新官方单格报告](https://github.com/huaweibei123/huaweicup2026/blob/e96a8551d6b3c92bbf00285376ce950f9246c0dc/results/a/q3-nikolastarx/pipeline-prefix-linux-20260925/receipt-public/REPORT.md) | 044/k5 的结构、容量守卫和38024周期为发布证据；本稿读取报告，不代签独立原件验证或完整算法 |
| §6.5.1 完整作业必要界 | [WHOLE_JOB_BOUND.md](https://github.com/huaweibei123/huaweicup2026/blob/09191c18bebc8b93e7751058b7c1b0f67c7d08fe/docs/a/q3-yuanzhifang/WHOLE_JOB_BOUND.md) | 067/k5 完整作业家族下界 12446880；不能超越已存 12237901；不证明全局最优 |
| §6.5.2 首波阶梯 | 源码 `68fbe66e97f78161bfb6f4f9e83cd2f0977ce7a9`；[当前保留的冷构造与停止记录](https://github.com/huaweibei123/huaweicup2026/blob/6152817144576bec9918a2ae59ef54e42352b21e/results/a/q3-yuanzhifang/wave-stair-20260925/REPORT.md) | 真实构造成功 1 次，随后父进程导入失败，0 E0；无官方分数 |
| §6.5.3 响应压缩 | `1b70dd6076430230c531b10e3e403e88474179cc` 的 `tail_response_model.py`；[真实图静态审阅](https://github.com/huaweibei123/huaweicup2026/blob/6152817144576bec9918a2ae59ef54e42352b21e/results/a/q3-yuanzhifang/tail-response-static-followup-20260925/REPORT.md) | 8804 操作与完整计算/FIFO DAG 一致；零 COPY/零额外 lag 模型，不是缓存模拟 |
| §6.5.3 阈值 DP | [TAIL_CUT_DP.md](https://github.com/huaweibei123/huaweicup2026/blob/2ec2ab12e1becdd600198eeb85deefc464678e9e/docs/a/q3-yuanzhifang/TAIL_CUT_DP.md) | 固定区间四系数表内精确；小表合成穷举对照；真实全区间表未完成 |
| §6.6.2 完整算法均值与墙钟 | [统一算法审计](https://github.com/huaweibei123/huaweicup2026/blob/cf4d77a018def540358c3b4667c2d2466390981a/results/a/q3-nikolastarx/forest-full500-feedback-20260925/independent-audit.json) | 500 格、973 在线 E0；本次独立重算 feed 墙钟/计数一致；共享主机单次分布 |
| §6.6.2 Cache 配对主表 | [配对审计](https://github.com/huaweibei123/huaweicup2026/blob/cf4d77a018def540358c3b4667c2d2466390981a/results/a/q3-nikolastarx/forest-cachepair-delta-20260925/independent-audit.json) | 476 同字节 P2 复用 + 24 新 P2，完整 500 对；不声称本批重新跑500个P2 |
| §6.5.4、§6.6.4 命中饱和 | [固定 Cache 事件审计](https://github.com/huaweibei123/huaweicup2026/blob/28e8c7ddfe2223b2261056f554259c43d5bba272/results/a/q3-nikolastarx/prefix-cache-critical-audit-20260925/REPORT.md)及 `summary.json` | 两份044/k5原结果在本次重新核 SHA、键大小/次数和事件：171首次miss、11重复hit、0淘汰；上界只针对固定读取集合 |
| §6.5.5、§6.6.4 共享前缀与路径 | [固定实际路径审计](https://github.com/huaweibei123/huaweicup2026/blob/28e8c7ddfe2223b2261056f554259c43d5bba272/results/a/q3-nikolastarx/prefix-realized-path-20260925/README.md)及 `audit.json`/`test_math.py` | 1678操作开始时间重现为团队已发布结论；本次复核分项算术，不重新构建准备图。36592仅有理数共享取整模型界，不登记为官方浮点剪枝证书 |
| §6.6.5 非单调反例 | [CACHE_NONMONOTONE_021.md](https://github.com/huaweibei123/huaweicup2026/blob/f26704ed8748f0a575b55f1a02b83d7335a1083f/docs/a/q3-yuanzhifang/CACHE_NONMONOTONE_021.md)，同提交 `audit_021.py`/`audit.json` | 同 plan 2140720→2140863、同 COPY/字节；已核字节原件及逐操作观察；尚非完整退化因果链 |

## 公式审阅与图件计划

Sol medium 只读复核了式（6-6）至（6-16）及相关小源文件，未运行真实图或 E0。两项意见已采纳：连续流水公式就地明确不同阶段使用不同核、同序通过且每阶段单作业串行；森林最优性在结论句中限定固定树/归核和不交错内部峰值模型。峰值符号改为 $h_i$，避免与计算时间 $p_i$ 混淆。此为团队内部复核，不标为独立盲审。

文档检查：正文16个公式编号连续、显示公式分隔符成对、六处图占位均明确标注，正文与索引的相对链接目标存在；小文件聚合脚本执行成功，正文数表和墙钟与固定输出一致。新增文件已检查个人绝对路径及凭据形态。当前平台为 Windows，没有 `dot_clean`；对本次写入的具体目录只读扫描，未发现 `._*`、`.DS_Store` 或 `__MACOSX`。未生成正式图片、PDF 或 TeX 排版，因此未声称这些产物通过视觉/版式验收。

2026-09-25T04:20Z 后续修订：再次核对 `311322b` 的 adaptive/guarded/gap/calendar/pipeline/witness/forest 实际调用关系，补入按顺序的结构路由表、一般 DAG 链与汇聚联合放置和构造复杂度边界。明确“严格接受”只相对于本次已成功评价的基准，基础路由没有跨历史算法的不退化保证；初始评价或程序错误不属于可静默回退的候选拒绝。同时补出首次装入闭式的递推与归纳理由，明确装入不能提前与上游重叠的抽象前提。均为已有源码/数学说明的完善，无新构造或官方调用。

本次完整 Mailbox 抓取 6 话题/667 评论、读取整个索引；继续仅按 P3 与公共协议清单补读，不宣称导入同账号所有专项历史。队长算法 HEAD 核对仍为 `e96a8551d6b3c92bbf00285376ce950f9246c0dc`，完整统一版本未变；保留本稿已有主表。

实际读取 [P1 固定 ad168d9e 的符号与跨问节](https://github.com/huaweibei123/huaweicup2026/blob/ad168d9e8dfe9e36a75503788a9f4852a1946729/paper/sections/P1-%E9%97%AE%E9%A2%98%E4%B8%80%E8%AE%BA%E6%96%87%E5%88%9D%E7%A8%BF.md)及 [P2 固定 87cd5d2d 的对应段落](https://github.com/huaweibei123/huaweicup2026/blob/87cd5d2d14db8de9ad0d7ab44f5e3a36c4ae6537/paper/sections/a-q2.md)后，发现各初稿尚未完全同名。P3 已在本人章节内消除与 P1 的 $\mathcal T$ 冲突，并与两问共有记号对齐；未修改他人文稿。合稿映射为：

| 对象 | P1 固定初稿 | P2 固定初稿 | 本 P3 修订稿 |
|---|---|---|---|
| 可提交方案 | $P=(\phi,\kappa,\sigma)$ | $\Pi=(\mathcal S,c,\sigma)$ | $P=(\phi,\kappa,\sigma)$ |
| 分区含义 | $\phi$ 的非空原像组成 Task 集合 | $\mathcal S$ 为子图分区 | $\phi$ 的非空原像对应 $\mathcal S$；每核合并 Task |
| 张量集合 | 与 Task 集合 $\mathcal T$ 分开 | $T$ | $T$，不再用 $\mathcal T$ 表张量 |
| Pipe 与有效周期 | $p(v),d_v$ | $p(v),d_v$ | $p(v),d_v$ |
| 固定 A 场景单核分母 | 固定官方基线 | $A_i$ | $A_i$；JSON 源字段 `B_over_M` 是同一分母的旧命名 |
| 求解、外部复评墙钟 | $T_{\mathrm{solve}},T_{\mathrm{E0}}$ | $\tau_{\mathrm{solve}},\tau_{\mathrm{E0}}$ | $T_{\mathrm{solve}},T_{\mathrm{E0}}$ |

P1 正文核编号从 1 起，P3 对齐接口从 0 起；只是编号映射，合稿时需统一，不应改变各自等待语义。P2 的整体方案符号和时间符号可由队长最后统一，不为了形式一致改写它的实质模型。主表数据和源 JSON 字段未因记号调整改变。

新增小范围原件复核：`python -B paper/tools/audit_p3_prefix_cache.py`，输出[前缀 Cache 核验](../drafts/p3-prefix-cache-audit.json)。只读取固定提交中的两份 P3 压缩结果（48,921 B 和 50,375 B）、一份计划、两个审计小文件；结果/计划 SHA 与已发布绑定一致。独立核实了完整键—大小—次数多重集相等、首次/重复读取、命中字节上界取等、零淘汰和搬运字段一致。对路径部分只核来源绑定、38024分项和、8244差值及四个前缀完成下限算术；未重新加载完整准备图，也未调用Task/Step/E0。七处图占位与18个公式对应最新稿，旧“六图/16式”是上一版检查记录。

| 图号 | 目前状态 | 最终绘制需要 |
|---|---|---|
| 6-1 技术路线 | 文字占位 | 冻结入口及模块归属；可编辑结构图 |
| 6-2 容量与切点 | 文字占位 | 044/k4 各候选固定元数据与真实峰值；估计/实测分开 |
| 6-3 核数与质量 | 文字占位 | 最终单版本完整100×5与基线绑定 |
| 6-4 Cache 分布 | 文字占位 | 同计划P2/P3；逐格 hit/miss 字节；保留负例 |
| 6-5 044 启动竞争 | 文字占位 | 实际时间轴、独占乐观值、条件共享模型界分别标识；不画成三个实测算法 |
| 6-6 021 事件差异 | 文字占位 | 对齐原 timeline；未有关键路径证明时不能画成因果结论 |
| 6-7 质量—墙钟 | 文字占位 | 固定硬件/worker 的端到端计时；重复试验与跨用例分布分开 |

按用户要求，当前不生成看似实测的示意数据。最终科研图使用项目 `scientific-figures`/Matplotlib 工作流，保留绘图输入、脚本和可编辑来源，待算法冻结后绘制与视觉验收。

## 后续更新规则

1. 先取得队长发布的固定算法 SHA、入口与完整结果版本，再检查其相对于本稿的模块和语义差异。新研究分支、少量成功格或成绩台逐格最佳，不能自动替换完整主表。
2. 结构改动同步修改假设、公式、伪代码和复杂度；对旧证明审查是否仍适用，不只更新结果数字。
3. 指标至少保留 Makespan、总额外搬运、同计划 CacheGain、字节命中率与完整求解墙钟。比较版本时固定图/核数/配置/官方源码身份，缓存收益固定计划身份。
4. 容量或单尾扩展只有完成官方验证并进入冻结统一入口后，才迁入主算法描述；局部实测、静态分析、理论必要界始终单独标明。
5. 发布修订使用新提交和原任务 Issue 通知队长，等待对方实际读回或合稿回执；发送成功不当作已采纳。用户目标为持续跟进算法和修订论文，本次初稿交付不表示该持续目标已经完成。
