# A 题正式任务板接入

本轮 project 为 `huaweicup2026-a`，同步分支为 `atlas/a-2026`。这是独立于已结束预演的新业务空间，不复用预演任务或被撤销的权限。

公开邀请在 `atlas/a/invitation.json`；以队长 NikolaStarx 发布的任务 Issue 中固定提交链接为信任来源，核对真实 Issue 作者、仓库、project、epoch 和公钥指纹。私钥、session URL、完整私有状态不上传。不要从远端快照覆盖队长权威模型。

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

按 `references/task-board.md` 使用签名 `task.set`；字段版本读取 `team state` 的 `task:<task-id>:<field>`，不是整图 cursor。只在开始、受阻和交付时维护。交付请求一次包含 review 与 PR 引用，队长独立验收后 done。

排队/上传不代表 accepted；收到回执后回读目标。权限不足、冲突或未回执分别记录，不删状态绕过、不重建身份、不将旧状态冒称新任务进度。没有后台 Agent 唤醒；Mailbox 由成员本人启动的 Agent 查收。

队长服务本轮按需运行，不安装永久服务。若队长暂离线，已发布指派仍可读，写请求可能待处理；先交 Issue/PR，下一次交接点处理同步，不把无回执当作任务已验收。
