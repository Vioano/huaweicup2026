# 会话登记入口

协议：[team-session-v1](SESSION_PROTOCOL.md)。可复制表单：[消息与交接模板](templates/SESSION_MESSAGES.md)。

唯一地址簿使用组织仓库的 **`[sessions] team-session-v1 会话登记与路由`** Issue，由真实队长账号 NikolaStarx（数字 ID `120649042`）发布。首次发现可执行：

```sh
gh issue list --repo huaweibei123/huaweicup2026 --state all --search 'in:title "[sessions] team-session-v1"' --json number,title,url,author
```

精确匹配标题并通过 API 核对作者。若出现多个同标题入口，不自行新建/任选，让既有调度会话给出固定入口；查不到时向原任务 Issue 请求链接。读取正文和全部分页评论，不能只依赖 Mailbox 的“最近消息”。本文件只保存稳定入口，不维护一张会过期的“所有会话都在线”表。

## 本轮迁移

- farmeruncle123 的任务通信继续用 [#14](https://github.com/huaweibei123/huaweicup2026/issues/14)，lyx0217 继续用 [#15](https://github.com/huaweibei123/huaweicup2026/issues/15)。任务 ID 不变；新 session 在登记 Issue 报到，在原任务 Issue 声明续接或子范围。
- 各账号的协调入口和专项 session 由实际会话自己登记。未知的旧会话不补造 session_id，不把同一 GitHub 作者的全部历史归到一个假定会话。
- 已有授权且正在执行的原 session，可用 `REGISTER + ADOPT` 一条消息登记现有分工，再由队长记录对应 assignment；不要求停止有效实验或等一轮空确认。新会话不能借“迁移”取得重叠写权。
- 发布协议的会话只负责协议设计、文档/PR及通知；原队长协调会话继续管理算法任务与 Atlas 权威状态。专项评审继续原授权范围。登记不转移队长职责。
- 旧 checkout 的 AGENTS 不会自动更新。通知固定 SHA 后先保留改动，再 fetch 并读取该版本；无需切换正在使用的算法分支或 Windows Atlas runtime。读完回报协议版本与**自己的实现 HEAD**，二者可以不同。

## 最短新会话提示词

> 读取项目 AGENTS.md、docs/SESSION_PROTOCOL.md 和 docs/SESSIONS.md。核对我的 GitHub 身份与本会话已有授权，生成并登记独立 session_key；不要接管同账号其他会话。先从当前任务/分工确认上下文模式与必读清单，再完整查收、按范围读原文。如本次是独立复核，先确认该聊天未继承开发讨论；只读约定输入，写入独立结果目录。已有明确授权直接继续，不因登记重复审批。先告诉我你负责的范围和上下文来源，再在任务 Issue 给实质回执。

没有明确任务时，完成只读预检并报告可承担范围；不凭最近 Issue 或 task=doing 自动认领。协议完整字段和冲突处理以 [SESSION_PROTOCOL](SESSION_PROTOCOL.md) 为准。
