# 队长首次启动提示词

将下面整段发给队长自己的 Agent，无需先替换占位符：

```text
现在测试开始。我是本次华为杯团队联测的队长。请在 huaweicup2026 项目读取 AGENTS.md、docs/rehearsal/START_HERE.md、RUNBOOK.md、RESULT_TEMPLATE.md，以及 .agents/skills/team-mailbox/SKILL.md、.agents/skills/system-atlas/SKILL.md、后者的 references/collaboration.md 和 references/task-board.md，按队长流程执行。

先只读预检，确认我的 GitHub 身份是 NikolaStarx、origin 是 huaweibei123/huaweicup2026，不能借用其他人的账号。检查并保留本地工作，沿用已存在且明确属于本轮的控制 Issue；没有才创建一个。生成唯一 run ID，发布本轮代码 SHA、实际截止时间、阶段表和公开邀请，给我可转发的 Issue 链接。队员以实际 READY 报到为准，不虚构名单。至少一名真实队员报到后列出名单让我确认“人员到齐”，再推进分工；这一步确认参加者，不是反复请求发信权限。

我授权你在本轮约 45 分钟内创建和更新本仓库的预演控制 Issue、向报到队员发送阶段指令和必要回复；建立本轮专属 Atlas 同步分支、工作区外的私有状态；核对成员公钥，发放本轮最小权限；创建任务、接收签名请求并验收；在自己的 codex/rehearsal- 分支提交测试报告、发起 PR。每个已授权阶段不必逐条重复请示。不要合并 PR、邀请新组织成员、改正式模型或开启永久后台服务。不要发出本轮范围外的消息，不上传私钥、令牌、session URL 或整个私有状态目录。

按 RUNBOOK 协调：双向 Mailbox 挑战消息；逐人创建和授权 Atlas 任务；让队员实际计算、交付脚本/结果/PR；核对同版本 Human/Agent 看板；在独立预演任务上测试越权、冲突与队长离线恢复。把 task 状态、已签名回执、实际执行结果和人眼验收分别记录，不能把“已指派”当作 Agent 已运行，也不能把 done 当作模型验证。

保持有限时的主动会话，每 20–30 秒查一次本轮新消息，长等待分段且向我报告有意义的变化；不得制造空回复循环。如果客户端无法保持活跃，明确告诉我说“继续本轮测试”即可恢复，不声称 Skill 能唤醒空闲 Agent。遇到真实权限或身份问题暂停相应阶段，其余可检查事项继续。结束时按模板汇总每人每项 PASS/FAIL/未测，给出证据链接，停止本轮 serve 进程并撤销本轮成员写权限，保留证据，不自动删除同步历史。
```
