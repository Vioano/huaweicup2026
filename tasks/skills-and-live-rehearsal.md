# 数模任务卡：Skill 更新与真机预演准备

负责人：@NikolaStarx（本次操作与联测队长）

分支：`codex/skills-and-live-rehearsal`

沟通 Issue：本次由用户会话授权；尚未启动真实联测控制 Issue。

1. **任务目标**：安装用户指定 figures4papers、更新 Atlas 0.5.0、准备不同 Agent 可执行的 Mailbox/Atlas 联测。
2. **输入文件**：固定上游 Skill 提交，现有团队协议；合成 `tests/rehearsal/observations.csv`，秒/米，非赛题数据。
3. **输出要求**：完整 Skill、来源/许可/哈希、队长与队员提示词、阶段手册、未预填通过的结果表、只读预检和本地 CLI 预演脚本。
4. **限制条件**：不提前发消息、初始化真实团队或增加成员；私有状态不入库；不把本地测试当真人多机器验收；不安装其他候选 Skill。
5. **验收标准**：固定版本文件一致；Atlas 91 项回归及实际 CLI 预演通过；模型验证通过；支持矩阵（Atlas macOS/Linux）的 GitHub CI 通过，原生 Windows 限制明确记录；用户日后按文档开展真实联测。
6. **截止时间**：准备工作本轮完成；真机联测由队长召集后以控制帖带时区截止时间为准。

## 交付记录

入口：`docs/rehearsal/START_HERE.md`；实际验证见 `docs/rehearsal/VALIDATION.md`。

实际多设备、GitHub 同步和人眼网页验收：待真实队友参加后执行，不计入本次已完成项。
