# E1/E2 早期评估材料：发布映射与补归档

本次补齐 2026-09-23 固定 FAST `d83d5f32a1c23f6450aa9c15fa85891c4ebddd7f` 的旧研究材料。**不是新实验，不更新算法成绩，也不把早期代理 E2 的结论套到后来原生 E2。** 原工作区、正式源码、现有算法和运行任务均未修改。

来源是旧独立工作区的 `output/assessment-20260923/`；归档者为 `nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。逐项映射、原字节 SHA-256、大小、已有固定提交/ZIP 成员及本次补交位置见 [publication-map.json](publication-map.json)。

## 核对结果

本次读取该目录现存的56个文件，包括被 Git 忽略的科研日志；这与“Git 未跟踪且无独立 blob”的审计口径不同，不能把压缩包内成员误判成全部未发布。

| 归档前状态 | 文件数 | 证据与处理 |
| --- | ---: | --- |
| 已有 origin 可达独立 Git 原件 | 6 | 交接报告、清单、v2 ZIP、3个旧矩阵计划；逐字节核固定路径 |
| 已在发布的 v2 ZIP 内 | 38 | 含 ASSESSMENT、probe 脚本/结果/日志及同字节的大图计划；每个散文件与对应成员完全一致 |
| 本次新补原件 | 11 | 两份 cProfile、7份计时/回读 JSON/CSV、1份 profile JSON、旧版 ZIP，详见下表 |
| 不属于科学原件的个人会话状态 | 1 | SESSION_LOCAL.md 不上传内容 |

上表11项按实际文件分类为：2份 `.pstats`、6份 JSON、2份 CSV、1份 ZIP。另把已经在 v2 ZIP 发布的 [ASSESSMENT.md](originals/ASSESSMENT.md) 原字节展开为可直接阅读的副本；因此本 PR 新增12个载荷文件，不是12项此前未共享成果。缓存和操作系统元数据不作为科学证据；本次排除规则下未发现额外这类文件。

已有 v2 在 [固定提交63353fd](https://github.com/huaweibei123/huaweicup2026/tree/63353fd771b5c2e643ec25f39d61a0b1729347af/docs/a/research/20260923-evaluator-acceleration)；[PR27](https://github.com/huaweibei123/huaweicup2026/pull/27) 在本次核查时仍为 Draft/Open，分支 `codex/evaluator-acceleration-handoff-20260923` 已发布，但该提交不是本次 `origin/main=3f0004815ca1c8f1af14b4f77db652caa98b37ac` 的祖先。“已经发布”和“已经合入 main”分别记录。本地 v2 ZIP 与发布 ZIP 完全相同：SHA-256 `9301c536a119e0a8ca1d4b040836e1f95b551cae89ed7d71345e79bc7765945d`。

## 新补原件及已有输入

| 文件 | 保留的历史信息 |
| --- | --- |
| [e1-matrix/run.json](originals/e1-matrix/run.json)、[paired-timings.csv](originals/e1-matrix/paired-timings.csv) | 001/019/080 配对时长、配置/环境/源码与计划哈希、原完整比较结果标记 |
| [e1-large/run.json](originals/e1-large/run.json)、[paired-timings.csv](originals/e1-large/paired-timings.csv) | 003 补充大图的原始配对记录；不是事先冻结发布矩阵 |
| [e2-routes.json](originals/e2-routes.json) | 原 rank/event 路线的开发池、误差、路线计时和质量门槛失败 |
| [pool-readback.json](originals/pool-readback.json) | 同机64候选回读、比较及交替计时原记录 |
| [diagnostic-readback.json](originals/diagnostic-readback.json) | 用 E0 局部时长替换及同池最优统一缩放的诊断，不能当可部署/留出集成果 |
| [profile-readback.json](originals/profile-readback.json)、[case_001.pstats](originals/case_001.pstats)、[case_080.pstats](originals/case_080.pstats) | 热点回读及两份原始 cProfile，保留原调用关系和时间，不重采样 |
| [evaluator-acceleration-probe.zip](originals/evaluator-acceleration-probe.zip) | 被 v2 替代的旧容器，保留历史，不作为当前实施指导 |

三张矩阵计划在固定 `d83d5f32a1c23f6450aa9c15fa85891c4ebddd7f:results/a/exact/r20260923-e1-matrix/plans/`；003计划与 v2 ZIP 的 `probe/case_003.plan.json` 完全一致。映射文件给出逐文件路径和哈希，可重建本轮已有材料的对应关系，无需重新运行。旧原型依赖原目录深度及运行时字符串替换；归档目录仅供阅读，不把内含历史复跑命令当作本次执行许可。

旧 ZIP 与 v2 都含39个成员，其清单各列38个载荷，全部大小/哈希一致、没有漏列载荷。两 ZIP 之间只有 `ASSESSMENT.md`、`ACCELERATION_HANDOFF.md`、`HANDOFF_MANIFEST.json` 不同：v2 更正会话标识及第一阶段措辞并更新清单，其余36个成员字节相同。完整 ZIP 原字节均保留，未用重新打包冒充原容器。

## 阅读边界与检查

- 历史 `e2-routes.json` 的 `recorded_e0_seconds_over_route_median` 把旧 Windows E0 时间除以 Mac 路线时间；约506/468倍已经被 ASSESSMENT 明确排除，归档原件不使其有效。有效同机口径应读 pool-readback，且它也不包含完整求解端到端成本。
- 旧原型、失败、缓存零命中和内存局限保留，不改数字、不从摘要补造完整 E0 输出。此处只补现存材料；不宣称当时所有函数调用、完整输出或全项目研究历史均已留存。
- 两份 `.pstats` 各130条函数记录，可用标准库格式读取；其中含历史本机函数文件路径。因它们是分析定位的原始元数据，在团队私有仓库保留字节，未做路径替换；不把这些路径写成新程序依赖。个人会话状态未上传。
- 实际检查仅为固定 Git blob/ZIP 成员比较、原件复制后哈希、JSON解析、ZIP内部清单/CRC及成员路径检查、标准库 marshal 读取 profile 结构、凭据模式检查与人工内容核对。未发现匹配所查私钥/GitHub/OpenAI token/Authorization 值的内容；有限检查不声称覆盖所有秘密类型。
- 55份科学原件的源字节、大小、mtime 在复制前后保持一致。没有执行旧 probe 脚本、被审模块 import、solver/E0/E1/E2、编译或性能测试。文档检查、Git和镜像同步不是算法验收。

任务六字段：目标为补齐早期本地证据与发布映射；输入为上述固定版本、现存目录及已发布v2；输出为本说明、逐文件映射和12份原字节载荷；限制为原件只读、0新评价且不改现有开发；验收为身份/映射/版本关系可核对，不代签科学终验；交付节点为独立归档PR及组织/研究镜像固定提交回执。主库合入与成员实际补读由调度、归档审计分别跟进。
