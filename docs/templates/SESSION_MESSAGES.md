# Session 消息与上下文包模板

遵循 [team-session-v1](../SESSION_PROTOCOL.md)。所有示例值/占位符必须换成真实值；没有信息填 null/unknown，未做的检查不能勾选。YAML 仅供 Agent 阅读，没有自动执行器。

## 生成会话 ID

macOS/Linux/Windows 均可用已安装的 Python（命令名按本机实际 Python/uv 入口）：

```sh
python -c "import uuid; print('s-' + uuid.uuid4().hex)"
```

只生成一次并保存本机映射；原聊天恢复不每轮重生。assignment/request/message ID 可同法生成 `a-`/`r-`/`m-` 前缀。

## REGISTER / ADOPT

登记 Issue 评论中保留 `@收件人`，使已有 Mailbox 能发现；角色本人核对 `gh api user`。

```yaml
protocol: team-session-v1
kind: REGISTER-ADOPT
message_id: m-<uuidhex>
repo: huaweibei123/huaweicup2026
owner: <API login>
owner_id: <API numeric id>
session_key: <lowercase-login>/s-<uuidhex>
agent_id: <codex/workbuddy/实际客户端>
role: <coordinator/implementer/reviewer/researcher>
purpose: <本会话职责>
parent_session: null
replaces_session: null
task_ids: []
assignment_ids: []
write_scope: []
branch: null
head: <实际完整 SHA>
context_mode: <continue/fork/isolated>
context_sources: []  # 固定文件/交接/评论 URL，注明继承聊天范围
excluded_context: []
authorization: <本人已授权范围的脱敏摘要；无则写只读/未授权发信>
state: registered
updated_at: <ISO8601 含时区>
protocol_commit: <实际读过的完整 SHA>
read: []
unread: []
impact: <对当前实现影响或无影响依据>
supersedes: null
```

后续 UPDATE 引用原登记评论 URL，发有变化的字段及 updated_at/supersedes，不重新复制所有旧信息。关闭时列在途请求、交付和接手入口；无接手者写未分配。

## 任务消息头

```yaml
protocol: team-session-v1
kind: <ASSIGN/ACCEPT/PROGRESS/HANDOFF/TRANSFER/QUESTION/RESULT/ADOPT>
message_id: m-<uuidhex>
from_session: <owner/s-id>
to_owner: <GitHub login>
to_session: <完整 session_key 或 owner:* 或 *>
task_id: <稳定任务 ID>
assignment_id: <a-uuidhex；纯通知可为 null>
reply_to: <原评论 URL 或 null>
protocol_commit: <完整 SHA>
```

正文写目标、范围、固定提交/来源、实际证据、未验证项、下一步。ASSIGN 再附允许上下文、产物与验收；ACCEPT 附实际 HEAD/已读/影响及本人授权；TRANSFER 引用旧方停写、新方接受和在途请求处理。使用新的 message_id 发送新意图，发送结果不明先查看 GitHub 是否已存在该 ID；不要盲重发。

## 上下文包（已推送 Markdown 或任务 Issue 内）

```text
Task / assignment / from-session / to-session:
目标、非目标、修改范围、授权摘要:
上下文模式 / 继承 / 允许清单 / 排除清单 / 实际暴露:
固定输入、代码、契约、protocol SHA:
已接受决定（逐项原件链接）:
已验证（命令、环境、结果路径） / 未验证 / 已否定方案及原因:
当前分支和 HEAD / 未提交产物如何保全:
Atlas project / epoch / accepted cursor / 字段版本 / requestId 与回执:
在途工作和请求 / 旧执行者停写范围 / 新执行者待确认:
待决问题 / 下一项可执行动作 / 完成标准:
已读 Issue/评论 ID 与更新时间 / 未读与失效条件:
```

没有必要公开的本机路径、客户端 thread ID 和私有备份位置只留本机。不要将整份私聊、完整状态或未审阅日志当作上下文包。
