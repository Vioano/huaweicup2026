# team-session-v1 检查记录

范围：项目协议/模板，不改 Mailbox 或 Atlas 执行代码。基线 `6508e32`；检查日期 2026-09-23。

## 源码检查

- Mailbox state 位于 Git common dir，以 GitHub login 校验身份；`notified` 属账号共享提示缓存。`full_inbox` 不消费 Hook 通知、不将导出当作已读。因此新会话必须独立记录实际阅读，不能只问“有没有新提醒”。
- Atlas grant/request 已支持 agentId/sessionId；请求 context 的字段严格只允许这两项，每项至多 200 字符。receipt 保留 context。actor/requestId 不接受 `/`，session_key 应放 context，不放身份 ID。
- Atlas grant 按 actor 替换，task 字段授权按 actor 公钥判断；没有 session 鉴权或任务租约。`assignees` 是精确字符串过滤，可保留 login 并增加 session_key，但不等于授予权限。
- 多 session 共用私有状态必须沿用单 writer / CLI 转发；独立上下文不等于独立凭据或隐藏图谱内容。

## 桌面推演（协议覆盖，非多人真机测试）

| 情境 | 协议期望 |
| --- | --- |
| 同用户 E1/E2 两会话 | 不同 session_key/assignment、不重叠写范围；同 Atlas task 的三状态字段由一个汇总会话维护 |
| 同会话恢复/压缩 | 保留 session ID，重新 full 抓取并核对本会话阅读位置及当前 HEAD |
| fork 复用研究 | 新 session ID，标 parent 与已继承内容，不能自称盲审 |
| 独立复核 | 干净上下文、允许清单、独立结果目录，未导入开发推导；若已暴露则降为普通复核 |
| 仅 @用户 / 无 session 的旧消息 | 交协调入口消歧，不让多个会话同时修改 |
| 同范围两个 ACCEPT | 只有明确被选的 assignment 可写；冲突暂停重叠部分，协调者确认 |
| 原执行者失联，旧 Atlas 请求仍排队 | 不因超时自动抢占；明确撤销旧分工并核实在途请求/版本或专用 actor 权限 |
| 消息发送结果不明 | 检查原 message ID 是否已存在；不盲重发或用新 ID 绕开 |
| 缓存被其他窗口更新 | full 抓取 + 本 session 回执，不能以账号缓存推断已读 |
| Windows Atlas 当前受阻 | Issue/PR 继续，保留 pending；不把协议发布变成重建身份或修 runtime 的前置条件 |

## 验证边界

协议不保证自动按 session 投递、持续收信、空闲唤醒、session 独占锁、上下文沙箱或同 actor 权限隔离。发布后按实际 Issue 回执分别记录发送、阅读和采用；不同成员新开聊天是否遵守、Windows/多设备使用仍需实际回报。

本机兼容检查已通过：直接调用现有 Atlas `validateRequest`，验证带 session_key 的请求可接受、未知 context 字段拒绝、含斜杠 requestId 拒绝；调用 `projectTasks` 验证 login/session 双标签均能过滤、其他 session 不命中。未向真实 Atlas 提交写请求，不以这些机制检查代替跨用户采纳。

9 份变更文档的本地文件链接存在性检查与 `git diff --check` 通过。对本次文档目录执行普通 `dot_clean docs tasks`，退出 0，扫描未见 AppleDouble/DS_Store。此次仅文档变更，未重复运行算法实验；远端 CI 以 PR 当前提交的实际结果为准。
