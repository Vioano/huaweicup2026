# team-session-protocol：多用户、多会话协作

负责人：@NikolaStarx。
执行会话：`nikolastarx/s-3fc95a987ee644f084188885526867be`，仅本次协议设计、发布与通知；原调度会话继续协调算法任务。
分支：`codex/session-protocol-nikolastarx`。
通信：[会话登记 Issue #26](https://github.com/huaweibei123/huaweicup2026/issues/26)，成员原 Issue #14 / #15。

1. **任务目标**：让队长精确区分用户与执行会话，合理复用/隔离上下文，避免同账号抢任务和重复写入。
2. **输入文件**：现有 AGENTS、TEAM/TEAM_WORKFLOW、A 题任务与 Atlas 接入说明、已安装的两个 Skill 文档/源码、当前邮箱消息。
3. **输出要求**：session-v1、AGENTS 启动规则、内嵌登记/消息/交接示例、固定提交 PR、现有通道通知与回读证据。
4. **限制条件**：保留队友工作区、任务和权限；不改 Atlas wire protocol/runtime，不共享凭据，不声称行为规则是运行时隔离/自动投递。
5. **验收标准**：覆盖身份、路由、状态、同范围单写者、分叉/续接/独立复核、handoff/失联、在途请求、阅读去重、Atlas 映射和迁移；兼容性与边界检查有证据；通知确实发出，成员已读另以实际回执核实。
6. **截止时间**：本次会话内发布并通知；队友回复时间未知，不以未回复推断已采用。

## 交付记录

- 源码检查：Mailbox locations/collect/full_inbox；Atlas validateRequest/validateGrant/prepare/receipt/projectTasks。现有验证器实测 session context 接受、未知 context 字段和斜杠 requestId 拒绝、login/session 双标签精确过滤通过；未向真实 Atlas 发测试写请求。
- 用户要求轻量化后，移除另立的消息/分工 UUID、独立模板与验证文档；直接复用 GitHub 评论 ID/时间，协议只在项目入口补充，不改 Skill。
- 内容为项目协议与文档模板，未变更算法、依赖、Skill 代码或冻结原件。
- 本会话上下文为既有项目规则与全邮箱历史（3 个话题、142 条评论的 2026-09-23T13:25Z 抓取）；不属于 isolated 复核。
- 发布、通知与采用状态以登记 Issue / PR 的固定提交及回执为准，不从此静态任务卡推断在线状态或队友已读。
