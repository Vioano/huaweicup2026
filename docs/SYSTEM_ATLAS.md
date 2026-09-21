# System Atlas 0.4.0 项目接入

安装位置：`.agents/skills/system-atlas/`。当前版本固定于上游提交 `f70784c1250679b57e4de516b07d9c00677acc69`，文件清单见 [system-atlas-install.json](system-atlas-install.json)。用户指定的本地源码与该远端提交一致；不自动追随上游 main。

## 用途

它维护系统模块、接口、关系、设计说明和证据，让网页与 Agent 查询同一份已确认模型。设计完成、实现完成、测试通过和真实运行分别标记。

0.4.0 新增团队协议：队长电脑保存权威模型；队员可以在授权节点和字段上提交签名请求或批注；队长按权限与读取时的字段版本处理，返回生效、拒绝或冲突回执。GitHub 传递请求和签名快照，远端快照不反向覆盖队长模型。

这些能力服务于设计协作，不会自动唤醒 Agent 或替团队调度建模任务。team-mailbox 仍负责 Issue 消息和成果交接。

## 本机使用

需要 Node.js 18+ 和 Git。本次安装验证及项目 CI 使用 Node.js 22。完整 Skill 已随仓库提交，队友克隆后可让 Agent 读取 [SKILL.md](../.agents/skills/system-atlas/SKILL.md)，Codex 下轮可以发现它。

从项目根目录运行：

```sh
# 检查随附演示模型
node .agents/skills/system-atlas/bin/system-atlas.mjs validate .agents/skills/system-atlas/examples/service.system.json --repo-root .agents/skills/system-atlas --json

# 启动本机预览，按终端提示打开 URL；Ctrl-C 停止
node .agents/skills/system-atlas/bin/system-atlas.mjs preview .agents/skills/system-atlas/examples/service.system.json --repo-root .agents/skills/system-atlas
```

内置示例是演示数据，不是华为杯项目的真实设计。项目模型由后续具体设计任务创建，不在安装时猜测赛题或团队架构。针对本项目模型使用 `--repo-root .`，不要沿用示例的根目录。

开发依赖只在维护和运行测试时需要：

```sh
cd .agents/skills/system-atlas
npm ci --ignore-scripts
npm test
```

`npm test` 是上游维护的 81 项回归测试，含 16 项团队协议测试。它们使用临时目录、本机 HTTP 和本地 bare Git 远端；不能代替真实队友电脑与 GitHub 网络互通测试。其他继承自 Archify 的测试不属于此命令选定的回归集合。

## 实际启用团队协作

先阅读 [团队协议](../.agents/skills/system-atlas/references/collaboration.md)，确定设计模型、队长、成员公钥与节点/字段权限。队长和每个成员各自使用工作区之外的私有状态目录，绝不提交私钥、私有状态或成员缓存。

上游 `team` 命令支持 `init-leader`、`init-member`、`grant`、`request`、`sync`、`serve` 等操作。团队同步默认使用独立的 `atlas-sync` 分支；`serve` 运行期间才持续同步。离线请求等待队长恢复处理，冲突后要重读字段并重新判断意图。

本次仅安装并验证完整 Skill。没有初始化本队 Atlas 身份、授权、模型或同步分支，没有创建常驻服务，也未进行真人多设备验收。具体初始化命令采用上游协议，使用本队确认后的真实参数。

## 更新与验证

更新前检查上游提交、团队协议变更和本地修改；通过项目分支与 PR 更新完整目录，同时更新来源清单。当前目录为完整上游副本，避免直接修改其代码而丢失版本对应关系。

CI 配置见 [.github/workflows/system-atlas.yml](../.github/workflows/system-atlas.yml)。它在实际安装目录执行依赖还原、回归测试和示例模型校验，结果见 [GitHub Actions](https://github.com/huaweibei123/huaweicup2026/actions)。安装验证不包含新增网页交互验收；上游已有浏览器记录保留在 Skill 内，不能当作本次重做的验证。

2026-09-21 本次安装验证：macOS、Node.js 22.22.3；`npm ci --ignore-scripts` 成功；`npm test` 实际通过 81/81（包含 16 项团队协议测试）；示例的 3 个视图分别通过 9/9 校验，0 错误、0 警告。230 个安装文件与固定上游版本逐字节一致。以上均为本机安装/机制验证，未运行真人多设备或本次浏览器交互验收。
