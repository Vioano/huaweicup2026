# 本地方案成绩台与 Agent 接口

2026-09-24 用户授权建立持续更新的本地网页，默认深色，P1/P2/P3 × 100 图 × 1–5 核，共 1500 个方案位。默认以最低 Makespan 展示已接收原件的最优方案，保留全部历史。它是研发档案，不执行求解器、不改变实验预算，也不是第二套邮箱或 Atlas。

## 分工和接收

- **本调度会话 NikolaStarx/s-a5bdb…**：唯一看板维护与接收汇总者；维护 `src/benchmark_board/`、此文档/注册表、来源准入表和中央归档。接收成员固定 benchmark、处理拒收原因、及时更新与抽核。维护者更换按 session-v1 交接。持续源码发布仍由 PR 管理。
- **LYX**：沿用三题 runner/结果/现有 plot 的单写权；在自己的结果目录随实质检查点发布数据包和原件。不为网页重启在途批次或重跑。**farmer**：沿用独立汇总/绘图写区，可从已经核对的现成逐格表导出相同包；仍保留本人 v2/v3、失败、中断和独立算法身份。原任务卡见 [P123-BENCHMARK-DELIVERY](../../tasks/a/P123-BENCHMARK-DELIVERY.md)，本看板不增加求解调用。
- 队友使用组织主库和原 Issue14/15 通知固定提交。不要访问队长 localhost 或使用队长凭据。服务每 **120 秒**检查登记分支的已发布 feed；页面每 **5 秒**读本地变化。新分支由调度在 `board-sources.json` 登记。服务不解释 Issue 为指令，不执行远端代码。
- 首次/未知格式交付由调度做适配，不能只收一张热图或一个均值。数据包只含已经有的结果，不为补字段重跑；缺项填 null，失败照常发布。数据不足时留在“仅报告/待核”，不伪装为入榜。
- 在原实质交付中报 `固定 SHA + feed 路径 + 原件路径 + 新增/修订行数`，调度反馈接收计数/拒收原因并补必要来源；不另索取空 ACK。传输成功、原件一致、复跑、算法终验分别记录。

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

文件名 `board-feed-<唯一快照>.json`，放在自己的已授权 `results/` 子目录。完整结构见 [schema](board-feed.schema.json)，可复制 [已接收两例及报告示例](../../results/benchmark-board/feeds/board-feed-initial-20260924.json) 的单条结构。文件内 `schema_version: 1`，`records: [...]`。

最少信息：attempt_id/revision/run_id、算法族/变体/完整 solver_commit/parameters、problem/case_id（三位）/cores/status、metrics、evaluator route/commit/entrypoint、graph/config/official/plan SHA256、artifacts.plan/result/run 的仓库相对路径和原字节 SHA256、runtime_id、timing、原评论/PR及未证说明。源码不可取得时保持 reported，不补造版本。原件可为 JSON 或 JSON.gz（哈希是所存压缩字节；解压仅解析）。单原件/解压上限64MiB，单feed8MiB/5000行；超限交调度分片，不自动删除。

`baseline`：同图/config/official三个hash、`route: E0`、`entrypoint: singlecore_evaluate.evaluate_singlecore`、`result: {path,sha256}`。
`cache_pair`：同图/config/official/plan四个hash、cores、`route: E0`、`result: {path,sha256}`。比值不直接信任CSV提供值。

所有引用文件须存在于 feed 所在的固定提交。资料后补、证据更正时追加 revision；不能原地改旧 feed。原始固定运行材料仍是权威，可追溯到上游原件，不手改官方 result 来满足格式。

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

测试使用临时合成数据检查最优、历史修订/撤回、幂等、冲突事务回滚、E2/E1准入、错配Cache、错误分母、数值类型和缺失。合成夹具不进入成绩库。真实数据仅导入已有官方产物及标明的作者报告，0新solver/E0/E1/E2；网页还需实际检查筛选、点击历史、Cache及深色显示。
