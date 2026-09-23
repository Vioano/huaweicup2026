# 多用户、多 Agent Session 协议

版本：`team-session-v1`。2026-09-23，队长要求将会话分工、上下文复用与隔离纳入项目协作，并知会成员。适用于本项目所有客户端；上游 Skill 和 Atlas wire protocol 的版本不变。入口：[登记与迁移](SESSIONS.md)、[消息模板](templates/SESSION_MESSAGES.md)。

## 1. 现有能力与本次补充

| 层 | 已有实现 | 本协议补充及实际边界 |
| --- | --- | --- |
| Team Mailbox | GitHub 账号认证、Issue/评论、完整抓取；状态在 Git common dir | 正文携带 session 地址、登记和回执；脚本不解析或自动按 session 投递，共享通知去重不是各会话已读 |
| System Atlas 0.5.0 | actor 公钥认证、任务字段授权/CAS、签名请求 `context.agentId/sessionId`、回执保留 context | 同一账号可标记多个 session 的来源；context 自述不构成新凭证，不限制该 actor 的其他会话 |
| 任务与代码 | 任务卡、PR、独立分支/worktree、Atlas 任务板 | 为任务增加执行会话、分工编号和交接记录；不会自动创建进程、锁、租约或访问隔离 |

源码依据：Mailbox `scripts/mailbox.py` 的 `locations/collect/full_inbox`；Atlas `team/protocol.mjs` 的 `validateGrant/validateRequest`、`team/member.mjs` 的 `prepare`、`team/leader.mjs` 的 receipt、`design/tasks.mjs` 的 `projectTasks`。路径均相对各 Skill 根目录。当前协议是可由 Agent 执行的协作约定，不宣称已增加运行时调度器。

## 2. 四种身份不要混用

| 字段 | 规则 |
| --- | --- |
| `owner` / `owner_id` | `gh api user` 的真实 login / 数字 ID；同一用户可有多个会话。收到消息核对 API 的实际作者，正文中的自称不是认证 |
| `session_id` / `session_key` | `s-` + UUID 的 32 位小写 hex；公开地址为 `lowercase(login)/session_id`。ID 不含秘密、任务含义或平台信息；全局寻址时再带 `repo` |
| `task_id` / `assignment_id` | task 是稳定工作项；assignment 是此次具体执行分工，包含会话、范围、基线和验收。换执行者或改变范围生成新的 `a-UUID`，旧编号保留 |
| `atlas_actor` / `agent_id` | 前者是既有注册公钥的 actor；后者是实际客户端，如 codex/workbuddy。更换模型不更换身份，模型未知就写 unknown |

`requestId`、GitHub 评论 ID、客户端 thread ID、实验 run ID 不是 session ID。Atlas 请求 ID 另用 `r-UUID`（符合其 100 字符及字符集限制）；不能把含 `/` 的 session_key 塞入 actor 或 requestId。

**生命周期：**同一个聊天恢复、上下文压缩、客户端重连保留 session ID；新聊天、fork、并发子会话各用新 ID，以 `parent_session` 或 `replaces_session` 关联。无法可靠确认原聊天身份时生成新 ID，不能猜测复用。已关闭 ID 不重新分配给另一个聊天。同会话改任务不必改 ID，但须结束旧 assignment、重新说明范围和上下文暴露；需要独立上下文就新开会话。

本机将 session_key ↔ 客户端 thread ID/工作区/阅读位置的映射存于 Git 工作区外的用户私有目录，每个 session 单独文件。不得写进共享 `.git/team-mailbox/state.json`，也不得把客户端 session URL/token、密钥、完整聊天或个人绝对路径贴到 GitHub。

## 3. 登记与状态

使用 [SESSIONS](SESSIONS.md) 指定的唯一登记 Issue，追加 `REGISTER` 评论；成员本人账号登记自己的会话。没有发信授权时先本地登记并说明“未发布”，不把团队通知当作本人授权。首次未参与的登记 Issue 不一定出现在 Mailbox 索引，须按入口直接读取正文和全部分页评论。

必填内容：owner/owner_id、session_key、agent_id、role、purpose、task_ids、write_scope、branch/HEAD、context_mode、context_sources、excluded_context、authorization、state、updated_at（ISO8601 带时区）、protocol_commit。暂无值写 `null` 或 `[]`，不能虚构已知客户端或任务。

- `role`：`coordinator` / `implementer` / `reviewer` / `researcher`；登记不改变本人已有权限。一个用户可以有一个协调入口和多个专项会话；队长也遵守。
- `state`：`registered` / `working` / `waiting` / `paused` / `closed`；仅报告当时工作状态。`waiting` 是等待具体依赖，`paused` 是已明确暂停，`closed` 是结束本会话职责，均不等于任务 done。
- 只在开始、任务切换、实质阻塞、交接、恢复和结束时追加 `UPDATE`；在正常进展消息中携带状态即可，不新增定时心跳。登记 Issue 可引用任务评论的固定 URL，避免复制进展流水账。
- 每条更新引用上一条登记/更新评论 `supersedes`。评论编辑只能勘误文字，状态变更追加新事件。两条并发更新引用同一前序时视为分叉，协调者明确解决，不能按到达先后静默覆盖。
- `updated_at`/GitHub 时间只表示最近声明。未回复或长时间不更新标“当前状态未知”，不能判已关闭、已释放或仍在线；需要调配时定向查询。

登记 Issue 是轻量地址簿与变更日志，不是第二份算法任务板。任务范围/验收仍由任务卡规定，进度仍由 Atlas 表达；冲突时报告并对齐，不随意选一个覆盖另一个。

## 4. 消息寻址、分工与冲突

继续一项话题一个 Issue、`@LOGIN` 通知。会话登记在登记 Issue；任务执行/交付在原任务 Issue。消息头使用模板中的 YAML 字段，Agent 阅读正文处理；不存在新 CLI 的 `--session` 参数。

- `to_session` 为完整 session_key、`owner:*`（该用户的协调入口）或 `*`（纯通知）。`to_owner` 与它一致。未知 session 先用 `owner:*` 请求路由；明确指定会话的消息，其他会话可转达但不得抢做。
- `owner:*` 由该用户已经登记的协调会话处理；没有协调入口时任一会话可以回报待路由或提名自己，不能据此执行未分配的修改。多个提名由队长在原任务 Issue 明确选定。
- `*` 广播只同步规则，不含“所有会话一起执行”的隐含指令。有行动时逐项指定 session/assignment；一条评论可列多个明确收件地址。
- 无 session 字段的旧消息按用户/原任务解释，供历史补读；如果已有多个候选执行者，先路由消歧。不要追改旧评论冒称旧 session 已认证。

**分工流程：**协调者 `ASSIGN`（session、task、assignment、write_scope、固定基线、预期产物/验收、允许上下文）；被选会话在本人既有授权内回复 `ACCEPT`（实际 HEAD、已读/未读、理解/影响、准备开始或阻塞）。已在本次用户指令中明确指定的工作可直接登记并 ACCEPT，无需额外审批或等空确认。

同一 task 可拆给多个 session，但每个 assignment 的文件/结果目录/共享字段写范围必须不重叠；一个 scope 只有一个被选执行者。公共文件或同一 Atlas task 的 status/blocked/deliverables 指定一个汇总写入会话。其他专项提交证据给它；不能靠“最后写入者获胜”汇总列表。独立评审可只读同一源码，结果写到自己的目录。

收到过期 assignment 的结果保留为候选证据，不覆盖现行分工或判定完成。冲突只暂停重叠写入，继续不冲突的已授权工作。独立分支不等于自动解决逻辑冲突。

**交接流程：**旧会话在原 Issue 发 `HANDOFF` 与上下文包，声明该 scope 停写及在途请求清单；新会话核对后 `ACCEPT` 新 assignment；协调者发 `TRANSFER` 引用双方回执，关闭旧 assignment 后启用新写入者。旧会话还可做其他未交出的任务。若旧会话失联，由其本人或有权队长显式撤销旧分工，保留工作区、先检查在途请求及最新字段版本，再指定新会话；超时本身不授权抢占。

这些是协作上的单写者规则，不是操作系统或密码学锁。Atlas 同 actor 的旧请求不会因为 assignment 撤销而自动失效；必须逐个确认 accepted/rejected/pending，必要时协调者通过现有字段版本变更使旧意图冲突，或明确撤销专用 actor 权限。没有查清在途请求时，不宣称已安全完成写权切换。

## 5. 上下文：默认最小充分，复用要有来源

| 模式 | 何时用 | 必须说明 |
| --- | --- | --- |
| `continue` | 同一任务续接、恢复、换会话接手 | 前会话、固定 handoff、已接受决定、未完成事项；重新核对当前消息、HEAD 和权限 |
| `fork` | 从已有探索分出方案、语言或实验路线 | parent_session、继承范围、分叉基线、独立输出目录；继承假设仍是待验证假设 |
| `isolated` | 独立复核、封存评价、与旧任务无关的新任务 | 干净新聊天、允许读取清单、禁止导入内容、实际暴露；不得从开发聊天 fork 后自称隔离 |

隔离分三层分别报告：模型上下文（是否继承/读过）、文件修改（worktree/目录）、权限（OS/凭据/actor）。worktree 不能清除聊天记忆，session 标签不能限制文件或密钥访问。需要严格盲审时在读取候选推导前明确允许清单；看过开发推导只能称普通复核，重新声明模式不能“忘掉”。同一账号可访问仓库的内容不代表该独立会话应该读取它。

**启动阅读顺序：**AGENTS/本协议/登记目录 → 本人授权与 task/assignment → 冻结输入/当前契约 → 固定上下文包 → 该任务新消息 → 为具体问题补读来源。对于 isolated，完整任务讨论可能污染判断，因此先读允许的任务卡/通知；仅按 allow-list 读取评论或文件，不先把整份聊天塞入上下文再过滤。

`check --full` 继续抓取完整用户邮箱并读取 index。随后：

- 协调会话读所有相关话题全文，包含登记与公共规则通知，维护全局路由。
- 普通专项会话读自己 task 的完整相关话题、点名自己的请求和公共规则；无关任务只看索引，不导入正文。isolated 进一步以 allow-list 选择原文，未读部分交协调者筛查是否有必须转达的契约更正。
- 用户明确要求全部消息时读全，并记录该暴露使严格隔离失效；不要一面读全一面声称盲审。
- 既有 [补读通知](a/SYNC_UPDATE_20260923.md) 对原任务负责会话仍有效；专项分工可由协调者提供明确的必读子集，不让每个独立复核重复继承全部历史研究讨论。

完整抓取不等于完整阅读。每个 session 单独记录 Issue/评论 ID + updated_at（有编辑则重读，必要时记 body hash）、读取范围及缺口；不要用账号共享的 `notified`/`last_success` 充当 read cursor。恢复时再次 full，随后逐条比对自己的回执。检查指定 Issue 全部分页，不能只看“最近 20 条”；没有新消息不发空回信。

上下文包包含：目标/非目标、task/assignment/session 关系、已接受决定及原件链接、固定代码/输入/契约版本、实际验证/未验证、分支与未提交产物去向、待决问题/下一步、Atlas project/epoch/cursor 与在途 requestId、允许/排除阅读清单。代码/结果先发布后链接，个人临时路径留本机。跨账号只交这类可审阅的材料，不共享私钥或完整私人聊天。

**复用失效条件：**源码/输入/契约/权限/epoch 改变时，旧摘要与观察只作为旧版本证据；读取影响范围并重验相关结论。摘要链接断裂、版本不明或互相冲突时回到原文，不能补造结论。

## 6. 与 Atlas 的映射

默认保留现有 `actor=LOGIN` 和已登记密钥，不为每个新会话 init-member。同机经已有 serve/写锁与 CLI 转发访问同一私有状态，不复制私钥到多个 worktree，不启动第二个 writer；不同机器/不同安全域不能为省事复制私钥，应单独登记新 actor 和密钥。

成员 CLI 请求使用：

```json
{
  "requestId": "r-0123456789abcdef0123456789abcdef",
  "context": {
    "agentId": "codex",
    "sessionId": "lyx0217/s-0123456789abcdef0123456789abcdef"
  },
  "changes": [{
    "operation": "task.set", "taskId": "a-r1-fast-eval", "field": "blocked",
    "expectedVersion": 12, "value": "具体阻塞及其证据链接"
  }]
}
```

这是格式示例，不可直接发送。替换 session、requestId、值及**刚实际读取的字段版本**；整图 cursor 不是字段版本。assignment_id 与 requestId 的映射写在任务 Issue 回执；Atlas context 只接受 agentId/sessionId，不塞自定义字段。结果不明时重试相同 ID/载荷；冲突时重读意图后用新 ID，禁止仅改版本覆盖。

grant 的 sessionId 只能表达一项标签，反复 `team grant` 会替换整个授权，不能用来登记同用户多个会话。每个请求自己的 context 才是本次来源；网页保存/队长本地修改未必带该 context，必须用 Issue 回执补充操作者来源，不能伪称旧回执含有标签。

Atlas task `assignees` 保留原 GitHub login（大小写保持既有值，过滤精确匹配）。如队长需要在看板按会话过滤，可**保留原 login 并追加** session_key；随后 `team query --mode board --assignee SESSION_KEY` 可查到对应卡。这是可选展示投影，不是权限。详细 assignment/scope/最新转交事件链接放 task description，多个 session 不必复制任务/模块。只有独立验收的子工作才建独立 task。

**真正权限隔离**需要单独 actor/密钥与限定 taskGrants，通过现有可信 GitHub 通道核对，私有状态置于各自可控安全域；若要求同机抵抗另一进程访问，还需 OS 权限/隔离运行环境，单独目录本身不够。v1 不自动迁移既有身份、不保证同 actor 的 session 级拒绝。共享 Atlas 图谱也不提供按会话隐藏封存内容的读取权限，封存材料另在受控位置保存。

若本机 Atlas 受阻，继续 Issue/PR 交付，记 `atlas=pending/blocked`，由既有协调会话按授权汇总；不能重建身份、篡改快照或用未验签 replica 取代 accepted 版本。本协议不要求修理已知 Windows runtime 问题。

## 7. 验收与采用回执

分清：`sent`=GitHub 创建并回读；`read`=具体 session 引用固定 protocol commit、实际已读/未读；`accepted`=该会话接受分工且有本人授权；`completed`=产物达到 task 验收。Atlas 的 accepted 是图谱请求应用，不是接受算法任务或算法验收。

成员回 `ADOPT` 时附 session_key、protocol_commit、实际实现 HEAD、已读/未读、上下文模式/来源/排除项、任务/范围/授权、影响/冲突。未回应者保持“待采用回执”。本协议的发布与一次通信不能证明所有新会话自动加载 AGENTS 或自动唤醒；新会话仍由本人启动或既有明确授权的客户端机制启动。

后续修改规则必须新版本/固定提交+定向补读通知；不覆写历史版本或要求每次进展重新审批。协议登记没有改变代码验收、公共契约或消息权限。
