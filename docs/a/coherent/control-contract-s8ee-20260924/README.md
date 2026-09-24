# 共同求解控制层：静态契约交付

状态：**设计草案，未实现、未运行、未验收**。2026-09-24；owner `nikolastarx/s-8ee33b891eb94c529bf5be94bb5d8894`。

1. **任务目标**：把三问已有构造作为 seed/proposal 接入同一薄控制层，明确探索、精确接受与合法落盘的边界，不重写构造器或 s55 共享评估设施。
2. **输入文件**：公共目标/协议固定 `1ee2c271c43bb14dd6c5de6b9ca7041b55d80916`；Pro4 本轮建议、三问构造入口及 s55 设计的完整 SHA 和实际阅读范围见下表。没有执行 Pro 附件。
3. **输出要求**：[CONTROL_CONTRACT.md](CONTROL_CONTRACT.md) 与 [SEED_DOMAINS.md](SEED_DOMAINS.md)。包括身份、确认规则、成本/失败语义、源码适用域和待定接口；不交付运行代码或成绩图。
4. **限制条件**：唯一写区为本目录；独立分支 `codex/coherent-control-contract-s8ee`。本轮 solver、E0/E1/E2、目标模块 import、构建、probe、测试、Pro 请求均为 **0**；旧 P2 的 13 次额度封存，不启用 proposed96 或 D3–D8。
5. **验收标准**：逐条映射固定源码；明确源码事实、设计要求、未验证主张；向 s55 交接接口问题；只做文本/diff/文件引用检查，提交固定版本供调度审阅。完整实现、全域 seed、预算故障恢复与质量—时间收益仍需另行授权验证。
6. **截止时间**：实际接受 `2026-09-24T12:25:19Z`，约 30 分钟内交付，即 `12:55:19Z` / 台北 `20:55:19`；交付后停止本轮工作。

## 阅读与证据范围

| 输入 | 固定版本与实际已读范围 | 用途 |
| --- | --- | --- |
| 公共规范 | `1ee2c271c43bb14dd6c5de6b9ca7041b55d80916`：AGENTS、README、TEAM、SESSION_PROTOCOL、TEAM_WORKFLOW、OFFICIAL_OBJECTIVES | 所有权、官方目标、两种时间、归档约定 |
| Pro4 | `a84119e65c5c817e3c4f3e2c3ce446b8616a9d55`：`AI chats/20260924-Pro4-算法方案设计/README.md`；`回答原文-f0ff3669-20260924T121808Z.md` 全文 | 外层控制、保留 incumbent、探索 frontier 等是建议，不是验收结论 |
| P1 | `4dff90ef699fd51845cf482951e8477066f5f566`：`src/q1/search.py`、`src/q1/prototype.py` 全文 | 候选生成、隐含准备成本、确认/发布缺口 |
| P2 | `0b58c123cccf02fc993b741d79dcd8511e4dd38f`：`src/q2/construct.py` 全文 | 从图构造 seed 的实际边界 |
| P3 | `a4e7ee13310d693ec4fb5cc236669ceb3b172d1f`：`src/q3/solve.py`、`src/q3/construct.py` 全文 | 结构 guard、回退、一次官方确认及落盘 |
| 共享设施 | `abdfd31f358a035e5ecca3b0482a9d0881060ffe`：`docs/a/e2/CONCURRENT_EVALUATION_DESIGN.md` 全文 | 身份、祖先许可、预算、unknown、后端输出域；它也是未实施设计 |
| s55 本轮交付 | `bd7f116c303709b6933e8f6b73338c29d690bed1`：`docs/a/coherent/backend-capabilities-s55-20260924/README.md` 全文 | 固定能力/费用表、三项接口答复；本方未进一步重审其18份底层文件 |
| 官方指标 | `1ee2c271c43bb14dd6c5de6b9ca7041b55d80916`：冻结 P1/P2/P3 evaluator 的搬运统计段、P3 Cache 分流和命中率段 | 澄清次级指标含义；不是本轮完整重新审计 evaluator |
| 协作规范 | 项目内 team-mailbox Skill、system-atlas Skill 及 collaboration reference | 已读/已接手/设计/实现/验收分层；不写公共 Atlas |

本轮 `check --full` 于 `12:25:39–12:25:46Z` 抓取 6 个话题、391 条评论，完整读取索引；仅按专项范围读取公共路由及本人有关内容，**不声称已读全账号 391 条**。Issue26 公共路由读至 `5813928992`。没有导入 Pro 全部历史、执行附件或重启已封存实验。

## 交付说明

本次沿用同一 session 的 `continue`，正常 P2 职责保持；旧 P2 工作区固定 `74c46372faf5910b9b3cce6ad9a61a7e040b17aa`，接手时干净、无在途。本目录不转移 P1/P3 或基础设施写权。公共分工/Atlas、成绩台协议分别由既有 owner 汇总。

5～10 分钟是原题脚注的求解效率建议，不是硬淘汰线或速度终点。限制枚举次数不自动满足题意；控制层提供正确的成本与证据边界，不能替代有结构依据的候选算法。

静态核对不证明全量适用或实际提速。外部最终 E0 复评与求解器内部选优调用分别计时；一旦结果影响当前选优，其调用必须计入在线成本。原文和源码的固定链接集中于另两份文档。

本轮静态检查：15 个固定源码/能力文档链接均以 `git show SHA:path` 解析，行号锚点未越界；三份文档已人工回读。仅检查文本、引用、diff 与本目录元数据，没有 import 目标模块或运行算法测试。s55 三项接口答复已纳入契约第 6 节，属于设计对齐；实现仍待交付。接手范围登记见 [Issue26 回执](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5814244569)。
