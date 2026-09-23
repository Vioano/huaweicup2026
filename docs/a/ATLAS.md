# A 题正式任务板接入

本轮 project 为 `huaweicup2026-a`，同步分支为 `atlas/a-2026`。这是独立于已结束预演的新业务空间，不复用预演任务或被撤销的权限。

公开邀请在 `atlas/a/invitation.json`；以队长 NikolaStarx 发布的任务 Issue 中固定提交链接为信任来源，核对真实 Issue 作者、仓库、project、epoch 和公钥指纹。私钥、session URL、完整私有状态不上传。不要从远端快照覆盖队长权威模型。

## 已确认的核对通道（2026-09-23）

队长本人明确指定：**本项目公钥核对、公开身份交换和任务授权通知，直接使用 team-mailbox 已建立的 GitHub Issue 通道，不默认要求微信、电话或人工转述。** Skill 所说的“可信渠道”在本项目即为下述经身份核对的通道；不是要求 Agent 自动再增加一条带外人工审批。

队长账号为 `NikolaStarx`，GitHub 数字用户 ID 为 `120649042`。成员通过 GitHub API 核对 Issue/评论的实际 `user.login` 与 `user.id`，不能只信正文中的署名、@、Git 提交作者、其他成员转述或可替换的邀请文件。登录者也应先核对 `gh api user` 为本人。

本轮队长确认的公开身份锚点：

- 仓库：`huaweibei123/huaweicup2026`
- project：`huaweicup2026-a`
- epoch：`eadbcb5b-801c-4c49-803c-6816804268c9`
- 同步分支：`atlas/a-2026`
- 队长 Ed25519 公钥 PEM 原始 UTF-8 字节的 SHA-256：`25a1a154c1acdfb57bfdca5b318b4bc6de92284ac0a15a24ad18d324c5764b50`

成员核对队长在本人任务 Issue 中的确认评论与固定提交邀请，并独立计算上述 PEM 指纹。匹配后，已有本人任务/接入授权的 Agent 直接续接 `init-member`（已有身份则复用）、发布公开 `actor/publicKey`、等待队长限字段授权、同步和启动浏览器服务。队长核对公开身份评论的真实 GitHub 作者后录入权限。后续每条 Atlas 请求继续校验 Ed25519 签名、项目/epoch、字段权限与版本，不要求人逐次批准。

仅在作者/身份锚点不匹配、公钥或 epoch 出现未经队长确认的变更、超出已有任务权限，或成员本人明确保留了更严格要求时暂停对应步骤并说明具体冲突。更换密钥/epoch 必须由队长本人账号重新发布明确的旧值、新值与原因，不能静默覆盖。团队约定不冒充成员本人撤销其单独提出的限制；该例外也不能被泛化成所有成员都必须发微信。

本通道只交换公开身份和任务信息；私钥、session token、完整私有状态不发送。此约定不要求关闭 TLS 校验、清除 Agent 的安全守卫或扩大节点/任务权限。

## Windows 运行版本

当前 main 附带的原版 Atlas 0.5.0 在 Windows 的目录 fsync 存在已知问题。本轮 Windows 成员采用仓库已有兼容补丁的固定提交 **ac48eafa1dbc83d4b141741e9fe25ce0c59962fc**（PR #13，基于 PR #11）。它没有合入 main；运行补丁不等于整个 PR 已合并或在成员机器完成验收。

运行环境与做题工作区分开。保留原改动，从仓库执行：

```sh
git fetch origin codex/atlas-competition-stability
git worktree add --detach ../huaweicup-atlas-runtime ac48eafa1dbc83d4b141741e9fe25ce0c59962fc
```

目录已存在时先核对版本并复用，不覆盖。进入 runtime 工作区后，读取同一版本的 `docs/ATLAS_AGENT_GUIDE.md`、`docs/rehearsal/WINDOWS_COMPAT.md` 及两个 Skill。该 runtime 仅用于 Atlas；A 题代码在任务包/本人分支工作区开发。不要因为 runtime 中没有 A 题文件而切换或覆盖任务工作区。

macOS/Linux 可使用本任务包的 0.5.0 Skill；三方 task.set、邀请与签名协议一致，额外 Filter 能力不作为本轮交接前提。补丁保留文件 fsync 和签名/版本校验；Windows 的目录项断电持久性不宣称等同 POSIX。

## 首次接入

各成员选择用户目录下、所有 Git 工作区之外的新私有目录，例如 `~/.local/state/huaweicup2026-a/<本人账号>`。下面大写参数替换为实际路径/账号，命令在 runtime 工作区运行：

```sh
npm ci --ignore-scripts --prefix .agents/skills/system-atlas
node .agents/skills/system-atlas/bin/system-atlas.mjs team init-member --state "MEMBER_DIR" --actor "LOGIN" --invite "任务工作区/atlas/a/invitation.json"
node .agents/skills/system-atlas/bin/system-atlas.mjs team sync --state "MEMBER_DIR"
node .agents/skills/system-atlas/bin/system-atlas.mjs team query --state "MEMBER_DIR" --mode board --assignee "LOGIN" --detail full
node .agents/skills/system-atlas/bin/system-atlas.mjs team identity --state "MEMBER_DIR"
```

已经建立本 project 的身份就复用，不重复初始化。`team sync` 首次可能需要先建立远端缓存，以实际返回为准。回报本人任务 ID、实际已验签 cursor，以及 `team identity` 的**公开 actor/publicKey**。队长核对 GitHub 评论真实作者后，只给本人任务的 `status/blocked/deliverables` 写权限。当前指派没有虚构公钥，也没有预先授予未知身份权限。

有本人授权且需要持续网页时执行：

```sh
node .agents/skills/system-atlas/bin/system-atlas.mjs team serve --state "MEMBER_DIR" --interval 15
```

使用终端实际打印的本机网址；别人的 127.0.0.1 不能用于本机。首次接入或本机工具问题不阻塞已授权的规则阅读/profiling；先在任务 Issue 给出一次精确错误，不反复空等。

## 状态与交付

多会话使用 [session-v1](../SESSION_PROTOCOL.md#5-atlas-只使用现成字段)：复用既有成员身份，签名请求的 `context.sessionId` 填完整会话地址、`context.agentId` 填实际客户端。同 task 指定一个汇总写入会话，其他专项回交证据。标签不授予 session 级权限，不用反复 grant 或新建身份切换会话。需要真正的权限隔离时另行核对 actor/公钥并限字段授权。

按 `references/task-board.md` 使用签名 `task.set`；字段版本读取 `team state` 的 `task:<task-id>:<field>`，不是整图 cursor。只在开始、受阻和交付时维护。交付请求一次包含 review 与 PR 引用，队长独立验收后 done。

排队/上传不代表 accepted；收到回执后回读目标。权限不足、冲突或未回执分别记录，不删状态绕过、不重建身份、不将旧状态冒称新任务进度。没有后台 Agent 唤醒；Mailbox 由成员本人启动的 Agent 查收。

队长服务本轮按需运行，不安装永久服务。若队长暂离线，已发布指派仍可读，写请求可能待处理；先交 Issue/PR，下一次交接点处理同步，不把无回执当作任务已验收。
