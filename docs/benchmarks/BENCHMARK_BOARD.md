# 方案成绩台：协作、任务与数据入口

本文件是 **方案成绩台** 的统一入口。分配 benchmark、运行批次、交付数据或维护网站时先读这里，再进入所需协议或任务卡；AGENTS.md、TEAM 与工作流只索引此处，不另复制一套字段规则。

网站展示 P1/P2/P3 × 100 图 × 1–5 核，共1500个方案位，默认深色，以最低 Makespan 展示原件已核的最优方案并保留全部历史。网页服务本身不执行求解器；计算由独立批次任务调度，不能因有空格自动扩大预算。

## 从这里进入

- **交数据**：[统一交付协议](SUBMISSION_PROTOCOL.md)第1/6节是日常导出、预检和简短通知；第2–5节是首次接入/排错的字段参考。JSON格式仍为 `board-submission-v1`，不是手填问卷。
- **查格式与来源**：[schema](board-feed.schema.json)、[未运行模板](examples/submission-v1.json)、[算法来源注册表](algorithm-registry.json)。已有产物的导出、归一化、哈希与预检由生产方完成。
- **看官方目标**：[方案质量与求解效率](../a/OFFICIAL_OBJECTIVES.md)。Makespan、求解墙钟、外部复评耗时分别记录；不把评价核吞吐当完整算法提速。
- **查当前任务**：原任务卡和原 Issue 是固定范围、预算与交付的依据；[会话登记](https://github.com/huaweibei123/huaweicup2026/issues/26)用于找实际负责人。网站维护任务见 [BENCHMARK-BOARD-MAINTENANCE](../../tasks/a/BENCHMARK-BOARD-MAINTENANCE.md)。

## 谁负责什么

2026-09-24 用户明确由以下两会话共同维护成绩台，按写范围协作：

| 角色 | 责任与写范围 |
| --- | --- |
| 研发对接、任务分配与网站接收：`nikolastarx/s-7c98eab1093e485291eacb04fd7c59ff`，Codex任务 `01a0d351-128b-7c70-a64e-592214732edc` | 对接研发，把需要验证的方案落实为明确任务并分配；接收结果、把差异和失败反馈研发。单写 `src/benchmark_board/`、成绩台文档/注册表、来源准入、中央账本与服务。 |
| 本机批次调度：`nikolastarx/s-59ee5b053e1c48af8a64bc9ddb6ed5bc`，Codex任务 `01a0d386-b656-73c1-bb8f-8c6166633b72` | 调度已经明确的任务，在独立分支/目录维护 runner、原件和标准 feed，测量并发资源、逐批交付；由接收方校验上台。 |
| farmer、LYX及其他数据生产者 | 在本人授权的算法/runner/结果写区完成明确任务并导出数据；farmer 保留独立汇总及 v2/v3 历史，LYX保留三题runner和结果来源。原在途批次按原规则收尾，不因网站接入重启或追加评分。 |
| 原队长调度 `nikolastarx/s-a5bdb19389ee43d686b7976d3bcdf766` | 全组协调、公共TEAM/AGENTS/Atlas、科学复核路由、主线整合与研究镜像；不并行写中央网站和账本。 |

共同维护不表示同时覆盖同一文件、结果目录或账本。写权切换仍按 [session-v1](../SESSION_PROTOCOL.md) 交接；新数据来源由网站维护者登记。使用组织主库和原任务通道；farmer 沿 [Issue14](https://github.com/huaweibei123/huaweicup2026/issues/14)，LYX沿 [Issue15](https://github.com/huaweibei123/huaweicup2026/issues/15)，不要求队友访问队长localhost或使用队长凭据。

## 研发到成绩的反馈闭环

1. **明确要验证什么**：研发给出现有任务与固定可运行版本，成绩台对接方明确比较对象、图/问题/核数、参数预算和结果用途，再交给执行者。沿用任务卡，不另建一套表格；未确定的研究建议不能直接当全量批次。
2. **尽早跑出首批**：执行者按已授权任务做小批链路验证后并发调度；有资源余量时提高有效吞吐，记录真实workers/子进程和资源观测，不用session数或模拟核数冒充机器并发。失败、超时和退化照实保留。
3. **分批交原件**：首批完成即可在生产端导出并预检，交固定SHA和feed，不必等全批。后续分片接着交；补证修订已有attempt，真实重跑建新attempt。官方单核分母可复用同冻结身份的[已有100例产物](../../results/benchmark-board/official-singlecore-20260924/README.md)，真实P1/P2的k=1求解结果与该分母分开。
4. **校验并反馈**：接收方反馈新增/重复/入榜/仅报告/失败及具体原因；成功原件匹配才入榜，缺原件显示“缺原件”，其他待核原因可下钻查看。把同条件下的改进、退化、耗时和失败样本连同固定来源发回研发，决定下一个有价值的任务。

常规整理在生产端脚本化完成，不转移给接收方；已接收的历史旧格式及适配回执保留。既有结果缺文件时先补现存原件，不为凑字段重跑。服务每120秒检查登记分支的feed，页面每5秒读变化；轮询成功不等于新数据，也不表示另一Agent已读、接手或通过科学验收。

## 最优与历史

1. 默认只从相同 problem/case/cores、当前冻结图/config/官方源码身份的成功记录中选最低 `makespan_cycles`；int/float 不强转。并列按稳定内容哈希排序。其他指标跟随**同一赢家**，切换指标不拼接不同方案的最好数字。
2. 跨算法/版本的默认视图明确叫**历史最优组合**。用户用于看当前可用最优方案；不得把它汇总冒充某算法全 100 图实验。选择 algorithm/run 可查看单独来源。无法一眼比较不同大小图的绝对 Makespan 优劣；另看基准比、耗时和同格历史。
3. 每次尝试有稳定 `attempt_id`、`revision`；同 revision 内容改变拒收，勘误/撤回追加更大 revision，旧记录永久保留。最高 revision 决定本次尝试现状；失败/撤回不入榜，另一旧成功方案仍可成为赢家。重复导入幂等。
4. E0 的计划、结果、运行收据须有固定 Git 原件与 SHA256；结果 Makespan/类型/问题/核数要匹配。身份与原件一致不等于重新运行或独立证实成员电脑行为。E1 另须匹配队长 `board-calibrations.json` 明确的实现、问题、图集合、核数、配置和 runtime；初版准入表为空，不因名字 exact 放行。E2 仅存来源记录，不入正式榜。
5. 官方单核比值只由固定 `singlecore_evaluate.evaluate_singlecore` 的匹配原件计算；没有原件留 NA，不能用 stub 或优化算法 k=1 代替。
6. P3 CacheGain = **同图、同配置、同计划哈希、同核数的 P2 无 Cache Makespan / 当前 P3 Makespan**。配对不符留 NA；不是任取最好 P2 与最好 P3 相除。Cache 命中率用官方按字节字段。可查看热力比值及选中方案的双柱对照。P3 相对单核另列。
7. `solver_wall_seconds` 与 `evaluation_wall_seconds` 分开，`timing` 保留包含关系、精度及未知项；不据此自动相加。`ddr_bytes` 在 v1 明确映射官方 `data_movement_bytes.scheduled_copy_bytes`，UI 标“调度搬运”，**不将它宣称为 P3 实际物理 DDR 访问量**；`spill_bytes` 为 spill_added_copy_bytes。未提供物理 DDR 指标时不猜测。

## 算法命名

P1/P2/P3 是**问题/硬件语义场景**，不是算法名；E0/E1/E2 是评价后端，不是提交方案的方法。一个算法族可支持多个问题，同一问题可有多个算法。无需现在强行合并成一个大算法；日后统一入口可登记为 portfolio，并记录每格实际选择的子算法。

采用 `algorithm_id`（稳定方法族，kebab-case）+ `variant`（机制变体）+ `solver_commit`（完整实现 SHA）+ `parameters`（候选预算/seed等），独立 `run_id` / `attempt_id` 区分实验和尝试。核数与问题是单独字段。v1/v2 等友好名可附，但不能代替 SHA，也不能仅写“latest/best/P1”。预算/精确评分后端变化须分 variant/run，不把不同方法拼成一个实验。

| 方法族 ID | 人类名称 | 现有别名 / 当前范围 |
| --- | --- | --- |
| q1-bounded-search | 有预算结构候选搜索 | q1_search_32_seed0；P1，参数单列，propose+E0 与 search+E1 分变体 |
| q1-stage-plan | P1 已交付结构方案 | 固定历史计划集合，不能假称已经具有全图通用生成入口 |
| q2-contiguous-baseline | 拓扑连续块基线 | q2_contiguous_baseline；P2；不是 M1/M2 或双样本专项 |
| q3-structure-selected | 结构守卫选择构造 | q3_structure_selected_online；resource_word / affine_eighth 分变体 |

这是数据接收层注册，不重命名生产函数、文件或原实验。固定入口和 SHA 在 [algorithm-registry.json](algorithm-registry.json)。后续新方法按真实机制登记，不因尚无短名阻止发布。

## 成员数据包

数据结构、文件大小、原件引用、预检命令及通知模板统一维护在 [SUBMISSION_PROTOCOL.md](SUBMISSION_PROTOCOL.md)，此处不再重复字段清单。首次接入按该协议的标准模板；[历史初版feed](../../results/benchmark-board/feeds/board-feed-initial-20260924.json)只用于兼容追溯，不作为新交付模板。

## 本地服务

仅 Python 标准库，无新增安装或云服务。命令在仓库根执行，状态默认在不入 Git 的 `output/benchmark-board/`（SQLite WAL、原件内容寻址快照和接收状态）。首次导入既有固定 feed 后即可使用：

```sh
python3 src/benchmark_board/app.py --state output/benchmark-board import --commit <完整提交> --feed results/benchmark-board/feeds/board-feed-initial-20260924.json
python3 src/benchmark_board/app.py --state output/benchmark-board serve --port 52341
```

只绑定127.0.0.1；`/api/v1/health` 核实已有服务，避免重复启动。日志、PID与 service.json 记录在本机 output。关闭窗口不停止已启动的后台进程；电脑关机/进程结束后按记录恢复，不承诺 OS 开机自启。重启沿用状态目录，不清库。数据库可从固定feed和原件重建，不能用备份回滚覆盖新历史。

## Agent 接口

网页与 Agent 同数据/同选择器，HTTP 只读，无 POST 执行入口。发现页 `/agent`，机器 schema `/api/v1/schema`。

- `GET /api/v1/cells?problem=P1&case_id=002&cores=4&algorithm=...&run=...`：最优和覆盖；无筛选完整1500格。`include_reported=true` 只预览，不替换已入榜方案。
- `GET /api/v1/records?problem=P1&case_id=002&cores=4&offset=0&limit=100`：全部历史，含失败、旧版本和拒绝入榜理由，limit≤500及next_offset。
- `GET /api/v1/records/<id>`：完整来源、指标、参数与证据。
- `GET /api/v1/events?after=<cursor>&wait=20`：增量、可长轮询≤25秒，返回next_cursor；Agent持久保存cursor，不需循环导入全库。
- `GET /api/v1/catalog` / `health` / `blobs/<sha256>`：算法注册、接收健康、已取到原件。

CLI：`python3 src/benchmark_board/client.py cells --problem P1 --case 002 --cores 4`；`client.py watch --after 0`。服务不提供凭据、任意本机文件读取或远程运行。来源未更新时显示最近检查和实际数据记录时间，不能把轮询当新成绩。

## 验证边界

网站测试使用临时合成数据检查最优、历史修订/撤回、幂等、冲突事务回滚、E2/E1准入、错配Cache、错误分母、数值类型和缺失。合成夹具不进入成绩库；网站接收和只读预检不调用solver/E0/E1/E2。另行授权的benchmark任务按实际调用记账，不能把网站层0调用扩大为整个项目0计算。网页交互需实际检查，数据已上台不替代独立复跑或算法终验。
