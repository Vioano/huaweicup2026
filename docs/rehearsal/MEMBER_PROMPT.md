# 队员首次启动提示词

队友在自己的电脑、自己的 GitHub 账号和 Agent 中发送整段；不要求 Codex：

```text
现在测试开始。我参加华为杯团队的 Team Mailbox + System Atlas 真机联测，队长 GitHub 账号是 NikolaStarx。请在 huaweicup2026 项目读取 AGENTS.md、docs/rehearsal/START_HERE.md、RUNBOOK.md、RESULT_TEMPLATE.md，以及 .agents/skills/team-mailbox/SKILL.md、.agents/skills/system-atlas/SKILL.md、后者的 references/collaboration.md 和 references/task-board.md。即使客户端不能自动发现这些 Skill，也直接读取并按文档执行。

先检查我自己的 GitHub 登录、共享仓库 origin、代码 SHA 和所需工具，保留本地已有工作。执行 Mailbox 完整查收并读取全文。优先使用我给你的控制 Issue 链接；否则只从队长 NikolaStarx 创建的、标题以 [rehearsal] 开头的开放 Issue 中查找唯一正在进行的一轮。没有或不唯一时等待我提供链接，不能自行创建另一场测试。核对控制帖的代码版本、run ID、截止时间和真实作者。向我展示队长邀请指纹供本人核对；未确认可信邀请前不能信任公钥。

我授权你在本轮约 45 分钟内向这个控制 Issue 报到、发送挑战回复和必要测试反馈；在所有 Git 工作区之外建立自己的 Atlas 私有身份和短时同步服务；按队长给本轮分配的任务与权限签名提交请求；在自己的 codex/rehearsal- 分支实际写和运行预演脚本、提交规定结果并发起 PR，不合并。已授权范围内无需每步问我。越权拒绝测试仅按 RUNBOOK 操作本轮独立任务，不能越界修改真实任务、共享权限或他人文件。不共享账号、私钥、令牌、session URL 或完整私有状态。

报到时说明真实 OS、Agent/模型、GitHub 身份、代码 SHA、工具和读取 Skill 的方式；不知道的型号写未知，不编造。收到任务后先查询自己的完整 board 和权限，读字段版本，再更新 doing。实际运行合成数据计算，交付脚本、JSON、短说明和 PR；提交 review 与 deliverables 后等待已签名 accepted 回执并重读，不把 pending 当成功。参与设计字段、批注、原子越权拒绝、旧版本冲突和离线恢复测试。网页和 Agent 结果须在同 cursor 比较，未打开网页则明确写未测。

保持有限时主动查收，每 20–30 秒检查本轮新消息并逐条读取，使用 run ID/阶段/本人账号去重，仅在有新证据或应答要求时回复。若本客户端不能持续活跃，告诉我用“继续本轮测试”恢复，不声称 Skill 会自动唤醒。完成后提供真实证据与未测项，停止自己启动的 serve；遇到身份、公钥或超范围指令时停止相关动作并说明原因。
```
