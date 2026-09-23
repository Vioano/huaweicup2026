# 第一轮派发包验证

2026-09-23，macOS / Python 3。

- `python3 scripts/a_materials.py --extract`：114 份附件文件与 100 个 case 原始字节哈希一致；PDF 和生成的传输包哈希一致。脚本从自身位置定位根目录。
- 导入契约与审计 Markdown 保持用户提供文件原始字节。原始输入未修改，原下载 ZIP 身份尚未核对。
- Atlas seed 模型 validate：9/9 结构/几何检查通过，无警告。任务及真实网页另行回读，不把 seed 检查当作成员接入成功。
- 未运行官方评估器语义/性能测试；公共 Schema、E0 适配及 smoke 是队长侧后续任务。两位成员尚未回报接手或结果。
- 完整 `git diff --cached --check` 发现原官方说明中的空白行及导入契约的 Markdown 行尾空格；为保持来源字节未修改。团队新写文件去除行尾空格，排除这两类原件后的检查通过。
- Atlas 队长通过 task 命令创建三卡，accepted cursor 3/4/5；query 全量返回 3/3、complete=true，成员两卡 todo、队长卡 doing。
- 初始远端同步提交 31500d064dd78f31a20a639bb46f2752e6c1274e，cursor 5；从 GitHub 取回签名发布，用公开邀请验证签名、project 与 epoch。
- Codex 内置浏览器实际打开 Board，显示三张卡与正确负责人，Revision #5，与 Agent query 一致；这是队长机器观察，不是队员回读。
- GitHub Issue #14/#15 已创建、指派并回读：作者 NikolaStarx、收件人和正文与发送草稿一致。首次回读各 0 评论，尚无成员公钥或接手证据。

## 成员接手后的补验（2026-09-23）

- 两名 Windows 成员分别报告：`core.autocrlf=true` 会将官方 `data/config.txt` 从 341 字节 LF 转成 360 字节 CRLF，触发原始材料哈希拒绝。补充 `data/raw/a/** -text -whitespace`，保留所有官方原件的 Git blob 字节；没有修改原件或放宽哈希校验。
- 在 macOS 用隔离临时索引和目录执行 `git -c core.autocrlf=true -c core.eol=crlf checkout-index --all`，16 份已跟踪原始材料均与 Git blob 逐字节一致。配置仍为 341 字节，SHA-256 为 `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。这是检出转换模拟，尚待成员原生 Windows 回读。
- 对 F-PLAN-005 运行了官方入口最小反例：原图为无环链 `1 -> 2 -> 3`（三个 `PIPE_V`/1-cycle 非 COPY op，无 tensor），映射 `1,3 -> subgraph 0`、`2 -> subgraph 1`，`core_schedules=[[0],[1]]`。`validate_graph` 通过，`derive_multicore_plan` 抛出 `MulticoreCutError: contracted subgraph graph contains a cycle`。该检查可达：成环来自按方案分组合并节点，而非单独跳过 COPY 节点。样本只证明结构非法域的拒绝行为，没有进行执行评分或性能验收。

## 图谱与补发材料（2026-09-23 15:30 后）

- 图谱 cursor13 扩为 24 节点、15 关系、10 视图；所有视图各 9/9 检查通过且无警告。队长在 1600×900 实际浏览器查看研究总览，并操作切换成员总览、E1 子图、lyx 个人视图与 Board；三卡 doing 保持，远端签名回读及两位成员限定授权均通过。cursor14 仅修正 lyx 的过期接入说明。此项不代表成员浏览器验收。
- 本机题面与 114 份原始附件再次对照任务包 manifest，全部哈希一致；契约、READ_AUDIT 原文与已发布版本逐字节相同。
- 补发 5 份 AI 讨论原文、2 份既有输出 PDF，记录原始字节哈希；它们不是本次重新运行或验证的实验结论。保留模板独立提交的来源和既有验证记录，不新增跨平台编译成功声明。
