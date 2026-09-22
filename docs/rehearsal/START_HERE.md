# Team Mailbox + System Atlas 真机联测

**状态：预演材料已准备；真人、多账号、多电脑联测尚未进行。** 本文面向队长 NikolaStarx 和队友，约 30–45 分钟。至少两个人、两个 GitHub 账号、两台电脑；三人参加更能验证广播和不同 Agent 的协作。不要用同一电脑上的两个模拟身份充当通过。

## 到时候怎么开始

1. 每个人拉取包含本目录的同一项目提交，用自己的 GitHub 账号登录，保留本机未提交工作。先按下面的准备命令检查环境。
2. 队长把 [队长提示词](LEADER_PROMPT.md) 全文发给自己的 Agent；队友把 [队员提示词](MEMBER_PROMPT.md) 全文发给各自 Agent。首次需要这一步，将角色、范围和发信授权交给各自的 Agent。提示词已含“现在测试开始”。
3. 队长 Agent 创建唯一控制 Issue，把链接发给队友。队员 Agent 可以自动发现唯一匹配的 Issue；有多个或暂时没有时，等待队长提供链接，不能猜测。
4. 同一会话以后说“现在测试开始”或“继续本轮测试”即可沿用角色和 run ID。换 Agent/新会话时重新提供相应提示词与控制 Issue 链接。**短口令没有内置广播或唤醒能力**；每个人都要启动自己的 Agent。

这次仓库更新只准备材料，不会提前创建控制 Issue、Atlas 身份或后台服务，也不会替队长联系队友。

## 每台机器的准备

使用 Git、GitHub CLI、uv、Node.js 22+。支持有文件和终端工具的 Codex、Claude Code、其他 CLI/IDE Agent；无需同一模型。纯聊天客户端若不能运行命令、登录 GitHub 或保持进程，由本人执行相应命令，并在结果中标为“人工辅助”，不能冒充 Agent 自主完成。

从项目根目录逐行运行（macOS/Linux/Windows PowerShell 通用）：

```sh
git status --short --branch
git remote -v
gh api user --jq .login
uv sync --locked
npm ci --ignore-scripts --prefix .agents/skills/system-atlas
uv run python scripts/rehearsal_preflight.py
uv run python .agents/skills/team-mailbox/scripts/mailbox.py init
uv run python .agents/skills/team-mailbox/scripts/mailbox.py check --full
```

未登录则本人完成 `gh auth login --hostname github.com`；Git 推送认证未配好时按 GitHub CLI 提示设置（可用 `gh auth setup-git`）。先接受组织/私有仓库邀请。预检只读验证仓库、身份、读取权限、声明的 push 权限、版本和模型；**不能证明真实 Git 推送已成功**，这要在同步和交付阶段确认。

完整查收后读取返回的 `index_file` 以及全部 `threads` 文本，不能只看摘要。其他 Agent 不识别 `.agents/skills/` 时，明确让它依次打开 `AGENTS.md`、本入口、两个 Skill 的 `SKILL.md`，不用为了自动发现复制一套可能漂移的 Skill。

所有参与者确认同一代码 SHA，以及：

- Atlas **0.5.0**，上游 `fc258c92d12d36bc9fbbabe0713056958b6cc7e2`；0.4 客户端不能参加任务看板测试。
- Team Mailbox 固定提交 `77581d464fa8d1b0d2182c31bee4fb0a8e03c83a`。
- 本轮模型为 [system.json](../../tests/rehearsal/system.json)，初始任务为空，三个模块成熟度均未验收。
- 输入 [observations.csv](../../tests/rehearsal/observations.csv) 为人为构造的无噪声直线，单位为秒和米，不是赛题或真实观测。

## 要验收什么

| 项目 | 实际通过证据 |
| --- | --- |
| 多 Agent 能读同一约定 | 每人的身份、OS、Agent/模型、代码 SHA、Skill 来源一致；自动发现或显式读取方式记清 |
| Mailbox 真通信 | 各人从 `check --full` 找到本轮完整上下文，带挑战码往返，记录真实 Issue 评论 URL |
| Atlas 真连接 | 各自密钥、可信邀请、GitHub 独立同步分支；队员读到队长签名的已确认版本 |
| 任务分配与执行 | 队长创建任务并授权；队员读到任务、实际运行脚本、交付 PR；队长重跑并验收 |
| 状态/设计协作 | `task.set`、`field.set`、`comment.add` 的回执与回读，以及同 cursor 的网页/CLI 一致性 |
| 异常边界 | 越权整批拒绝、旧字段版本冲突、离线排队/恢复，没有误报“已完成” |

详细执行看 [RUNBOOK.md](RUNBOOK.md)，结果填 [RESULT_TEMPLATE.md](RESULT_TEMPLATE.md)。一个阶段失败就记录具体命令、错误码、影响范围并诊断，不把后续阶段全判失败，也不强行宣布全通过。只有通过的项可以写 PASS。

## 本机预演

```sh
uv run python scripts/rehearsal_smoke.py
```

它用临时目录、本地 bare Git、模拟身份执行实际 Atlas CLI，覆盖建任务、授权、签名请求、冲突、原子拒绝和同版本回读；退出清理临时状态。它不调用 GitHub、不发送消息、不驱动另一个 Agent，也不验证真实浏览器。此次实际运行结果见 [VALIDATION.md](VALIDATION.md)。
