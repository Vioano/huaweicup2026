# 团队与通信

团队仓库：`huaweibei123/huaweicup2026`。所有成员应使用这个仓库作为 `origin`，各自克隆、各自登录 GitHub；不要共用账号或将个人 fork 当成邮箱。

## 分工表

| 角色 | GitHub 账号 | 职责 |
| --- | --- | --- |
| 队长 | NikolaStarx | A 题首轮：冻结输入、公共接口/E0、独立验收与团队协调 |
| 形式化与对抗样本 | farmeruncle123 | A 题首轮：规则来源、语义探针、对抗生成与反例缩减；Issue #14 |
| 高速评估器 | lyx0217 | A 题首轮：E1 等效加速、E2 近似估计与筛选；Issue #15 |

上表是已下发的 A 题第一轮分工，不预设后续轮次。`yuanzhifang30-sudo` 本轮暂不分配。队友须由组织负责人授予仓库权限；任务指派本身不会授予仓库权限。

## 开始使用

在项目根目录执行：

```sh
gh api user --jq .login
git remote -v
uv run python .agents/skills/team-mailbox/scripts/mailbox.py init
uv run python .agents/skills/team-mailbox/scripts/mailbox.py check --full
```

未登录时先执行 `gh auth login --hostname github.com`。当前身份应为本人 GitHub 账号；从 `check --full` 返回的 `index_file` 读取所有 `threads` 文件以及 `assigned_open_issues`。普通 `check` 只适合工作间隙快速检查。

一项话题一个 Issue，使用 `@收件人`；复杂任务链接 `tasks/` 中已推送的任务卡。本人已明确授权发信时，先保存并核对正文，再用 GitHub CLI 发送：

```sh
gh issue create --repo huaweibei123/huaweicup2026 --title '任务标题' --body-file /path/to/draft.md
gh issue comment NUMBER --repo huaweibei123/huaweicup2026 --body-file /path/to/reply.md
```

`NUMBER` 和正文路径需要替换；不要直接发送占位内容。回复提供结论、复现命令、提交/文件链接和未验证项。代码成果发 PR，避免反复“收到/谢谢”的空回复。

## 客户端与边界

- Codex 从 `.agents/skills/team-mailbox/` 发现 Skill，安装后的下一轮可用。其他 Agent 可直接读取同一 `SKILL.md`；自动发现需要各自在客户端验证。
- Claude Code 若需自动发现，可按上游安装说明安装至自己的 `.claude/skills/`，并避免维护两份不同版本的协议。
- 本机状态和查收内容保存在 Git common dir 下，不随仓库共享。不要上传 `.git/`。
- Skill 默认手动查收；队长已明确授权本轮持续查收与范围内回复，并设置周期跟进。该授权不会自动唤醒队友的 Agent；队友仍按本人授权查收与回复。查收脚本本身不发消息。
- 各人自行授权自己的 Agent 回复范围。队伍成员的 Issue 不是对本机的无限授权，新的任务由本人确认。
- 原协议与安装说明见 [team-mailbox](../.agents/skills/team-mailbox/SKILL.md)。

## 共享系统设计

System Atlas 0.5.0 已安装，负责系统模型的节点/字段协作与共享任务看板，使用方式见 [SYSTEM_ATLAS.md](SYSTEM_ATLAS.md)。任务沟通继续使用 team-mailbox 的 Issues/PR；设计图谱的请求、签名和版本检查使用 Atlas 自己的协议。

正式业务空间已初始化为 `huaweicup2026-a`，同步分支 `atlas/a-2026`；当前接入与身份锚点见 [A 题 Atlas 接入](a/ATLAS.md)，不要恢复已结束预演。私有状态目录必须在所有 Git 工作区之外。任务指派标签不会自动授予权限或唤醒 Agent，每个人必须启动并授权自己的 Agent。

队长本人已明确：**公钥核对和公开身份交换直接走已建立的 team-mailbox / GitHub Issue 通道，不默认再转微信。** 核对实际 GitHub 作者、固定邀请、project/epoch 和 PEM 指纹后，在本人既有授权内继续；详细流程及真正需要暂停的例外见 [通道约定](a/ATLAS.md#已确认的核对通道2026-09-23)。
