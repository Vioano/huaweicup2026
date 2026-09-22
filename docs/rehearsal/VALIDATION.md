# 预演材料的准备验证

日期：2026-09-22。此记录来自本次实际执行；真人联测记录须另填 `runs/<run-id>.md`。

| 检查 | 本次结果 | 范围 |
| --- | --- | --- |
| Atlas 固定版本 | 0.5.0，243/243 文件与固定上游下载一致 | 不含本机 node_modules；哈希清单已提交 |
| figures4papers 固定版本 | 6 个 Skill 文档 + 根 LICENSE，7/7 与固定 SHA 原始文件一致 | CC BY-NC 4.0；没有安装新增 Python 运行库 |
| Atlas 依赖与回归 | `npm ci --ignore-scripts`；`npm test`，91/91 PASS | macOS，Node.js 22.22.3，本地临时目录/HTTP/bare Git |
| Team Mailbox 回归 | `uv run python -m unittest discover -s .agents/skills/team-mailbox/tests -v`，21/21 PASS | 本地脚本机制测试；不代表双人通信 |
| 预演模型 | `validate tests/rehearsal/system.json --repo-root . --json`，9/9，0 error/0 warning | 单 overview；visualReview=pending |
| 实际 CLI 预演 | `python3 scripts/rehearsal_smoke.py` PASS | 本地 bare Git，建任务、授权、签名接受、旧版本冲突、越权原子拒绝、同 cursor 看板回读 |
| 只读本机预检 | `python3 scripts/rehearsal_preflight.py` PASS | NikolaStarx 身份、仓库权限/读取、Skill 哈希、模型；运行时为未提交工作树，不冒充发布版本 |
| 真实收件箱完整读取 | 0 Issue、0 comment、0 assigned open，fetch_complete=true；已读空索引 | 当时实际仓库状态；没有发测试消息 |
| GitHub CI | 见本次 PR 的 Checks | 独立报告远端 CI，不替代真人联测 |

尚未验证：真人/多设备、多 GitHub 账号同步、其他 Agent 自动发现与执行、当前新版网页实际交互、成员实际 PR 交付和队长复跑、真实离线恢复。上游附带的浏览器验证文档不视作本次重做。

`rehearsal_smoke.py` 没有启动真实团队、没有调用 GitHub API 或发送 Mailbox 评论，也不验证其他人电脑的认证。真实身份、公钥和同步分支留待队长发送启动提示词后创建。此处没有预填任何真人 PASS。

## 发现的原生 Windows 阻塞

首次扩展 CI 到 Windows 时，上游完整 91 项测试结果为 **62 PASS / 29 FAIL**。主要失败为 `design/authority.mjs` 的 `atomicWrite` 对目录调用 `fsyncSync` 报 `EPERM`，涉及身份/权威状态写入，不能当作纯测试问题。另有测试使用文件 URL pathname 形成 `D:\\D:\\...`，报 MODULE_NOT_FOUND。[原始失败 job 与完整日志](https://github.com/huaweibei123/huaweicup2026/actions/runs/35709250687/job/106685553780)。

未修改上游持久化代码或跳过错误声称支持 Windows。Atlas CI 的支持矩阵明确限定 macOS/Linux；原生 Windows 预检明确报错，联测手册要求 Windows 队友在 WSL2 的 Linux 环境内运行（本次未替队友安装或实测 WSL）。原生 Windows 的项目 demo/Mailbox 检查继续保留。测试失败证据保留在上述历史 run，不能用新矩阵的通过覆盖这个限制。
