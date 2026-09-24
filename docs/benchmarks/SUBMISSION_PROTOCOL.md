# 方案成绩台：benchmark 统一交付协议

版本：`board-submission-v1`，2026-09-24。正式名称为 **方案成绩台**。本次仅精简操作说明和通知模板；JSON格式、校验器与入榜要求不变，已有导出器无需迁移。

维护与接收：`nikolastarx/s-7c98eab1093e485291eacb04fd7c59ff`（@NikolaStarx），[会话登记](https://github.com/huaweibei123/huaweicup2026/issues/26#issuecomment-5813828246)。原调度 `s-a5bdb19389ee43d686b7976d3bcdf766` 已交出网站代码、协议、中央导入与运行服务的写权，继续负责公共分工、Atlas、科学验收和主线整合。公共职责已合入 [主线1ee2c271](https://github.com/huaweibei123/huaweicup2026/commit/1ee2c271c43bb14dd6c5de6b9ca7041b55d80916)。数据生产、接收、上台、独立复跑、算法验收是不同状态。

**两位队友的 Agent 以后将 benchmark 统一交给本维护 session；我检查固定提交、格式与证据后更新方案成绩台。** farmer 沿 Issue14，LYX 沿 Issue15。原 runner/聚合/算法写区和预算不变；只导出现有结果，不为本协议重启、补跑、增加候选或改变超时。固定算法版本的任务卡仍决定实验范围。

## 1. 日常交付：导出 → 预检 → 通知

**生产方 Agent 负责导出、归一化、计算哈希及预检；维护者负责接收、校验和上台。** 第2–5节是首次编写导出器或排查错误时的字段参考，不是每次交付都要手填的问卷。

1. **脚本导出**：在本人结果目录生成新的 `board-feed-<UTC时间>-<唯一后缀>.json`，顶层为 `{"schema_version":1,"submission_version":1,"records":[...]}`；需入榜的成功记录引用同一提交内的最终 plan/result/run 原件。每次图/问题/核数/种子/重复实验一条，保留失败、超时和旧尝试。可从[未运行模板](examples/submission-v1.json)实现映射，但不逐格人工复制填写。
2. **只读预检**：在仓库根运行下方命令，按输出字段路径修复格式问题，并查看未入榜原因；不修改官方原结果来凑格式。
3. **提交并通知**：将 feed 与引用原件 push 到本人分支，按第6节发送固定提交和 feed 路径。算法、环境、覆盖、缺口等已在 feed/原件中记录的内容，无需在 Issue 再抄一遍。

```sh
python3 src/benchmark_board/protocol.py results/你的目录/board-feed-唯一快照.json --submission
```

Windows 可使用项目 Python 的 `python`。预检只在系统临时目录检查格式和现有字节，不写中央库、不执行 solver/E0/E1/E2、不连接网络。退出码1表示结构错误；`valid:true` 不等于可入榜，仍须查看 `eligible` 和 `reported_or_failed.reasons`。缺证据可以如实提交报告，不能把未知填成0或猜测值。

**重复工作在生产端自动化**：导出器对同一批次的算法来源、运行环境等公共信息配置一次，再展开到各条记录；逐例差异从原收据读取。同原因的未知项可由脚本生成对应 `missing_reasons`，但须逐项核实缺口，不能统一标未知来省略已有事实。实际 solver/runner/evaluator 版本不能用导出时 HEAD 代替。换了实际方法、版本或环境仍按第3节区分批次与尝试。

只需上传用于本次成绩的最终原件；逐候选大件、完整 trace 和诊断日志不作为每次上台的必交项，生产方仍按原实验任务保全。补证使用原 attempt 的新 revision，重新运行使用新 attempt；不为协议重跑实验。已接收的旧格式快照及适配回执继续保留，后续常规导出由生产方完成；具体映射有疑问时给出字段和来源样例，由维护者澄清规则。

维护者反馈接收条数、入榜/待核/失败数和原因，并登记新来源。运行服务每120秒发现允许分支的新 feed，网页每5秒更新；未登记分支或停机时不承诺自动收取。无需访问队长 localhost 或向网页 POST。旧 `schema_version:1` 数据兼容留存，新包声明 `submission_version:1`，不覆盖旧 feed。

## 2. 文件与编码

| 文件 | 格式、要求 |
| --- | --- |
| feed | UTF-8 JSON对象；≤8MiB，`records`≤5000条；按独立快照分片，禁止NaN/Infinity、字符串数字和布尔数字 |
| plan | 官方 `<case>_multicore_res.json`，顶层仅 `node_to_subgraph`、`core_schedules`；保持官方键/类型，不加网站元数据 |
| result | E0/E1实际输出的完整JSON；保留 `scene`、`num_cores`、`makespan`、全部搬运/Cache/诊断字段。官网源格式在冻结 `contest_io.py`/三题evaluate源码，网站不重写它 |
| run | 实际运行收据JSON，保留原结构；若旧收据已脱敏，记录派生说明及原文件保留位置，不反填后加保护措施 |
| trace / log / manifest | 可选诊断JSON、原始UTF-8日志、批次清单JSON；不缺省伪造。清单可引用旧CSV、基准失败列表和调用账 |
| 图表/CSV | 辅助成果，仍保留；不代替逐例feed与原件，不从热图颜色/均值推造逐格成绩 |

`artifacts.<名称> = {"path":"仓库相对路径","sha256":"64位小写SHA256"}`。路径用 `/`，允许 `results/ docs/ data/ tasks/`；不允许绝对路径、反斜线、冒号、`..`、`.git`或指向仓库外的软链接。所有引用须在feed的**同一完整Git提交**中可读；外部原件先保全到本人的授权结果目录。JSON可用 `.json.gz`，SHA256算所存压缩字节，解析上限64MiB；单原件也≤64MiB。超限交维护者协商分片，不删原件。

## 3. 完整字段字典

机器类型见 [board-feed.schema.json](board-feed.schema.json)。Schema声明结构；`protocol.py --submission`另校验字段间一致性、空值原因和证据。数组 `[]` 表示没有该项，`null` 表示未知/未测/不适用并说明原因；不得以0代替缺失。`unknown`仅用于必须为字符串而来源确实未知的字段，并在notes解释。

### 每条记录的身份与状态

| 字段 | 类型 / 含义 |
| --- | --- |
| `attempt_id` | 非空字符串≤200字符，全库唯一尝试名，建议 `login-run-P1-002-k4-seed0-repeat0`；重新运行换ID |
| `revision` | ≥1整数；对同一尝试补证/更正/撤回递增，旧版本保留。同ID同revision不同内容拒收 |
| `run_id` | 非空批次ID≤200字符；算法、版本、预算或运行环境改变建新run，不混合优胜格 |
| `algorithm_id` / `algorithm_name` | 稳定kebab-case方法族 / 可读名称。P1/P2/P3和E0/E1/E2都不是算法名 |
| `variant` | 具体构造、候选生成/选择政策；例如 `propose-e0` 和 `search-e1-e0-confirm` 必须分开 |
| `solver_commit` | 实际求解实现40位SHA；未知可null但只存报告、不入榜。不可用结果导出时的HEAD冒充 |
| `parameters` | JSON对象：完整实际参数（seed、候选预算、超时、后端、回退/停止策略等），保留原单位；空对象需说明无参或缺失 |
| `problem` / `case_id` / `cores` | P1/P2/P3；字符串001–100；整数1–5。模拟核数不是机器worker数 |
| `status` | `ok` 成功；`failed` 错误；`timeout` 超时；`running` 作者报告运行中；`not_run` 未运行；`unsupported` 不支持；`withdrawn` 撤回 |
| `runtime_id` / `observed_at` | 可追踪机器环境标签 / 原运行UTC时间或null；不写个人路径/IP/机器序列号，不用接收时刻填运行时刻 |
| `source_url` / `notes` | 原Issue评论或PR链接 / 字符串数组，说明缺口、偏差、历史更正和证据范围 |

同attempt的 problem/case/cores/algorithm/run/solver_commit不可改变。换方法/参数/机器或实际重试建新attempt；旧中断记录保留，不能因磁盘有best_plan就标成功。`ok`须有Makespan；其他状态最终Makespan为null。失败耗时保留，其数值指实际消耗而非合法方案完成时间。

### 数值、评价源和身份

| 字段 | 类型、单位、来源 |
| --- | --- |
| `metrics.makespan_cycles` | 正数，模拟周期；保留原JSON的整数/浮点类型，不四舍五入 |
| `metrics.solver_wall_seconds` | ≥0数或null，程序启动、读图、在线预处理/构造/评分/回退/确认到方案落盘及必要收尾的端到端秒数 |
| `metrics.evaluation_wall_seconds` | ≥0数或null，独立最终评价的实际秒数；不能用它代替求解wall |
| `metrics.ddr_bytes` | ≥0数或null；历史字段名，实际对应官方 `data_movement_bytes.scheduled_copy_bytes`，界面叫“调度搬运” |
| `metrics.extra_ddr_bytes` | ≥0数或null；官方 `data_movement_bytes.added_copy_bytes`，即总额外搬运，不等于scheduled总量 |
| `metrics.spill_bytes` | ≥0数或null；官方 `spill_added_copy_bytes` |
| `metrics.cache_hit_rate` | 0–1数或null，P3官方按字节命中率；不是百分数0–100或命中次数比 |
| `metrics.baseline_speedup` / `cache_gain` | 派生输出；接收器忽略上传值，以匹配原件重算，不把作者比值当真值 |
| `timing.solver_includes_evaluation` | true/false/null；说明所报evaluation是否已包含在solver wall内，不能自动相加 |
| `timing.evaluation_precision` / `utc` | 字符串或null，原计时精度及旧时区说明；真实新时间使用UTC的 `YYYY-MM-DDTHH:MM:SS[.sss]Z` |
| `evaluator` | `{route:E0/E1/E2, commit:40位SHA或null, entrypoint:字符串或null, calibration_id:可选字符串}`；最终给成绩的后端，与算法内评分后端分别记录 |
| `identity` | `graph_sha256/config_sha256/official_sha256/plan_sha256`：64位小写SHA256或null；official取冻结source-manifest的 `official_code_hash`，不能自行换成另一种拼接哈希 |
| `artifacts` | `plan/result/run`为成功入榜的必要原件引用；可加 `trace/log/manifest`。缺失时省略引用、记录原因，不能写假的哈希 |

前3个metrics键为新协议必需，未测写null。其余缺项可省略或null。附原result后搬运/Cache数字从原件重读；不会把P3调度搬运当作实际物理DDR访问量。`reported_baseline_cycles`/`reported_cache_ratio`仅为历史作者报告字段，不参与派生计算。

E0仍是最终官方确认来源；E1须匹配维护者校准表的固定实现/问题/图/核数/config/runtime，E2只存研发来源、不入正式最优榜。`artifacts_checked`只表示原件和声明身份匹配，**不证明运行收据语义真实、执行过未修改官方代码、算法合法性已独立复跑或科学验收通过**。`eligible/evidence/admission_notes/source/imported_at/id/sequence`由服务生成，队友不填写。

官方P3原件实际标识是 `scene:"B", problem:3, cache_mode:"read_only"`（冻结problem3源码684–689行）；不得改成scene C来迎合网站。P2同plan对照是无Cache的B结果，不含P3标识或Cache统计。网站场景名称“情况C”不是原件scene字段的值。

### `provenance`：谁的算法，谁运行，怎么运行

下列对象和列出的键均必需；未知使用schema允许的null，并在 `missing_reasons` 给出完整点路径及原因。

| 对象 | 全部字段与含义 |
| --- | --- |
| `producer_session`, `task_url` | 导出者session地址、原任务Issue链接；身份仍由GitHub实际发信账号确认 |
| `solver.source` | `{repo,commit,path,entrypoint}`或null；repo为owner/repo，commit须等于solver_commit，path是该提交中真实代码/固定历史计划路径，entrypoint为函数/CLI或null |
| `solver.authors`, `method`, `references`, `upstream` | 作者login列表；方法机制简述或null；论文/Pro/Issue来源链接列表（说明仅来源、非验收）；继承实现列表（每项同code_source四键） |
| `solver.selected_algorithm_id`, `selected_solver_commit` | portfolio/选择器本格实际子算法及其SHA，两者同时有值或同时null；固定历史计划应说明生成参数未知，不假称有通用solver |
| `runner.source`, `argv`, `working_directory` | 测试驱动四键code_source或null；实际argv字符串数组（记录、不执行）；仓库相对cwd或null。磁盘新代码不是旧进程的实际版本 |
| `environment` | `os,cpu,gpu,ram_bytes,python,dependencies,threads,workers,peak_rss_bytes`；文本项为字符串/null，内存和并发数为非负整数/null。依赖可写锁文件SHA和编译器版本；无GPU写“none”，未知null |
| `measurement.started_at`, `finished_at` | 原始开始/结束UTC时间或null；不以文件mtime或Git时间猜测 |
| `measurement.seed`, `repeat_index`, `cold_start` | 整数/null随机种子；从0开始重复编号；true/false/null冷启动，不能混合冷热计时 |
| `measurement.solver_scope`, `evaluation_scope` | 计时起止与包含范围的文字说明或null；明确在线E0已计入求解，额外baseline/P3配对不冒充solver wall |
| `measurement.budget` | `{wall_seconds,candidate_limit,stop_reason}`；非负数/null、非负整数/null、字符串/null，写实际原授权预算/停止原因 |
| `measurement.calls` | `{solver,E0,E1,E2}`；各非负整数/null，记录真实启动调用（失败/超时/未知不能漏账），不把次数当效率目标 |
| `measurement.offline_costs` | 离线训练、编译、预计算成本/身份/摊销范围说明或null；明确无则写“none”，不隐藏针对当前用例的工作 |
| `measurement.failure` | 成功/未发生失败为null；failed/timeout/unsupported/withdrawn必填 `{stage,reason,exit_code,elapsed_seconds}`，后两项可null。中断原因放这里，旧attempt另保留 |
| `missing_reasons` | `{ "provenance.environment.cpu": "旧收据未记录", ... }`。provenance中未知null均须逐项解释；failure/未选子算法的null除外 |

算法注册表是[当前已识别入口](algorithm-registry.json)，不是禁止新方法的白名单。新增算法在首次交付写上述source/authors/method/upstream，我核对后登记；同算法改变实现记录新SHA，改变机制记录新variant/方法族。代码源URL固定为 `https://github.com/<repo>/blob/<40位SHA>/<path>`。原研究建议、作者报告与实测字段分开；E0/E1/E2只标评价来源，不能替代求解算法身份。

## 4. 基准与P3配对

`baseline`和`cache_pair`省略或null表示尚无有效原件；超时/失败清单放run/manifest，不能伪造成功引用。结构如下：

```text
baseline = {graph_sha256, config_sha256, official_sha256,
            route: "E0", entrypoint: "singlecore_evaluate.evaluate_singlecore",
            result: {path, sha256}}
cache_pair = {graph_sha256, config_sha256, official_sha256, plan_sha256,
              cores, route: "E0", result: {path, sha256}}
```

baseline必须为冻结官方单核A结果，不能用stub或优化solver k=1代替；P1/P2均值为逐例B/M的算术平均，报告有效n/100，缺项不算0。P3配对必须是本条同图/config/official/plan/核数的P2无Cache结果，CacheGain为P2/P3，不能取两张独立最优表相除。P3相对单核是另一个指标。网站当前不代做全100均值验收。

维护者可将同一冻结身份的已核官方单核分母补给已有记录，无需重跑多核。对于缺少多核原件的E0报告，所得加速比仅在“包括仅报告”预览中显示，并明确“分母已核、分子仍为报告”；`eligible`不因此改变，不能当成正式成绩。单核基准只运行一次并共享，不冒充P1/P2两次求解器运行。

历史最优组合可跨算法选每格最低Makespan，但它不是一个算法的完整实验。比较耗时须核环境、线程、冷热、预算和计时范围；不同条件只并列，不宣称程序提速。官方5–10分钟是效率建议，非600秒淘汰线，也不是研发停止点。方案质量与端到端耗时分别持续比较。

## 5. 接收、修订与复核

- 结构错误拒绝整feed并给字段路径；同attempt/revision冲突拒绝事务，不能部分覆盖旧历史。重复相同记录幂等。
- 原件缺失/哈希错/版本或冻结身份不符，保持报告及原因；错误冻结身份不进入当前矩阵的预览候选。失败/超时不会出现在最优榜。
- 成功原件匹配才入榜；同格最低Makespan获选，其他指标跟随同一计划。相同Makespan按稳定内容ID选择。E1准入范围外/E2不入榜。
- 补证或纠正旧数字：新的feed、更大revision、notes引用旧版本及更正理由；撤回用withdrawn，不删旧文件。重新运行用新attempt并保留旧成本。
- 维护回执列 `固定SHA / feed / 收到行数 / 新增与重复 / eligible / 待核及失败 / 拒收原因 / 页面可见范围`。Git送达、格式通过、网页可见、原件一致、独立复跑、算法终验逐项说明，不互相代签。
- 该协议只收可共享结果；不收账号凭据、个人机器绝对路径或原始题面重复副本，不改变Actions停用规则。

## 6. 队友Agent的简短发送模板

数据先 push，再发到本人原 Issue（farmer #14，LYX #15）。沿用 session/to/task 路由，只报告交付入口、实际预检和本次变化；不另做一份与 feed 重复的算法/环境/覆盖清单：

```text
@NikolaStarx
session: <你的实际session>
to: nikolastarx/s-7c98eab1093e485291eacb04fd7c59ff
task: a-benchmark-board-maintenance / <原benchmark任务ID>

数据: board-submission-v1；<分支> @ <40位SHA与组织主库链接>；feed=<仓库相对路径>
预检: <实际命令、退出码；输出可附文件路径/固定链接>
说明: <新增结果/补证/更正/撤回，以及未在feed记录的异常；无则写无>
```

不另发空ACK；在下一次实质交付带实际已读协议版本和影响即可。此通知不证明队友Agent已经读取或采用；我按实际回执跟进。
