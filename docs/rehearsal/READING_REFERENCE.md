# Agent 读取命令与评分对照（作答后核验）

以下都接在命令前缀后：

```sh
node .agents/skills/system-atlas/bin/system-atlas.mjs team query --state "PRIVATE_DIR" --cursor C --max-bytes 8192
```

将 PRIVATE_DIR、C、LOGIN 换成本人真实状态目录、刚读取的数值 cursor、实际已分配任务的账号。CLI 帮助里的 team 模式列表较简短，但 `reach/path/cycles` 实际通过相同查询引擎支持；本项目探针会实跑确认。

| 目的 | 参数 |
| --- | --- |
| 顶层总览 | `--mode overview --depth 0 --detail summary` |
| 模块与直接子层级 | `--mode local --target analysis --depth 1 --hops 0 --detail summary` |
| 只取一个模块全文 | `--mode local --target analysis --depth 0 --hops 0 --detail full` |
| 下游可达性 | `--mode reach --target data --direction out --kinds dataflow` |
| 最短路径 / 不存在的跨层路径 | `--mode path --from data --to delivery --kinds dataflow`；第二次把 to 改为 baseline |
| 成环区域及语义过滤 | `--mode cycles --kinds dataflow,feedback`；对照 `--kinds dataflow` |
| 网页同一展开范围 | `--mode view --view overview --expanded analysis` |
| 任务过滤 | `--mode board --assignee LOGIN --detail full` |
| 全量分页审计 | `--mode full --detail full --limit 2`，重复相同参数并追加返回的 `--page TOKEN` |

正常工作不需要按此表把所有策略跑一遍。复用 manifest 与已确认范围：先总览，按问题取局部或任务，发生变化再读增量；只有明确全量审计才读 full。

### 正确性标准

- Q1：顶层 `data / analysis / delivery`；analysis 聚合包含自身和三个子节点。内部边因折叠未显示，不等于不存在。
- Q2：analysis 的直接子节点是 `baseline / residuals / revision`；跨边界连接保留 data、delivery 的外部 ID。自身全文与带子层级的范围不同，不混淆 depth 与沿关系扩展的 hops。
- Q3：dataflow 可达集合包含起点 data、analysis、delivery。包含关系不会隐式成为 dataflow，不能声称 baseline 已收到实际输入。
- Q4：data → analysis → delivery；data 到 baseline 无显式路径。path 返回一个最短跳数见证，不是全部路径或运行时因果。
- Q5：含反馈边时，baseline/residuals/revision 构成一个循环强连通区域；仅 dataflow 无环。结构成环、图谱版本都不能证明业务反馈闭合或真实执行。
- Q6：同 C、同展开范围是 6 个规范节点与 5 条规范关系；任务卡不自动作为图节点。缩放、位置不同不改变这些事实。
- Q7：与已确认 board 及真实授权区分；assignees 不授予权限，也不证明 Agent 在线；protocol 的 `entities: []` 合法，done 不提升模块成熟度。
- Q8：从首页到末页固定查询和 C，按类型+稳定 ID 检查无重复/遗漏，与 manifest 规模及任务数对应。`selectionComplete` 指后端选择完成，`complete` 指本响应是否包含整个选择，最后一页也可能 complete=false；需要 `page.hasMore=false` **且已收齐前页**。更改查询后复用旧分页 token 应明确拒绝，不能悄悄得到混合结果。

按每题“策略选择 / 事实准确 / 范围与版本 / 局限说明”各记 PASS、FAIL 或未测，保存一句实际回答。关键误解（把包含当数据流、环当真机闭合、pending 当生效、漏页当全量）必须纠正后用具体重读结果复验；不要用 Agent 自报“我理解了”验收。
