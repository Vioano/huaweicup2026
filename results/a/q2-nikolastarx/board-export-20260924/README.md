# P2 历史 13 次尝试：方案成绩台 v1 交付

1. **目标**：按成绩台研发对接任务要求，将已有 002/044、4 核的全部 13 次官方调用及原件导出；本次新增 solver/E0/E1/E2 调用均为 **0**。
2. **输入**：历史归档固定 `74c46372faf5910b9b3cce6ad9a61a7e040b17aa` 的 `results/a/q2-nikolastarx/joint-20260924/`；实际旧运行 `73e40f6ddcb8fd6a8f45a3120dbc7f82875ec628`；Fang 历史 seed `0b58c123cccf02fc993b741d79dcd8511e4dd38f`。协议固定 `c4ec05fd34edfcf144434fcdc182b30b4a82caf8`，`board-submission-v1`。
3. **输出**：[完整 feed](board-feed-20260924T132237Z-history13.json)、[预检回执](precheck.json)、生产端导出器 `src/q2_nikolastarx/export_board.py`，以及同提交中逐字复制的历史原件。93 个归档文件、3,441,456 字节均与固定原提交逐字核对一致。所有原件保持原字节，包括 gzip；`run` 指向真实整批 ledger，本条位置在 parameters 中说明。
4. **限制**：只写本人结果区与导出器；不改算法、官方程序、成绩台代码/协议/中央库。旧 13 次已用完封存，导出不重新评价、不新增候选。
5. **检查**：导出器检查历史归档字节、原 manifest、原输入及 as-run 源码 hash、plan hash、压缩与解压结果 hash、指标/数值类型、ledger 对应关系及确认重复。原 v1 预检结果 `valid=true, records=13, eligible=13, reported_or_failed=[]`；这是格式/原件核对，不是独立复跑或科学终验。
6. **交付节点**：本轮全 13 条一次交付，固定提交发布后交成绩台维护者核收；是否入库/页面显示以其回执为准。

## 结果与方法身份

| 方法来源 / variant | 002 / 4 核 Makespan | 044 / 4 核 Makespan |
| --- | ---: | ---: |
| Fang 固定历史 M1 | 72415 | 74530 |
| Fang 固定历史 M2 | 未在本批评价 | 69113 |
| 本机固定 M1 分核，singleton + id | 72415 | 125366 |
| 同上，critical32 | 72634 | 74099 |
| 同上，critical | 72056 | 74099 |
| 同上，earliest_start | 92004 | 71242 |
| 最终独立重复确认 | 72056（critical） | 69113（旧 M2） |

`q2-fang-stage-b-frozen` 是固定历史计划来源，variant 为 m1/m2；不把它伪装成当前通用求解器。`q2-fixed-assignment-priority` 对应本机 `FixedAssignment.build`，四个 variant 分开记录，实际源码 SHA 为 73e40f6。最终确认沿用被确认方法的身份与 variant，使用新 attempt、repeat_index=1，保留其选择来源。

13 次真实调用中有 10 个不同 plan hash；044 critical32/critical 生成相同计划，但真实调用两次，不能删掉成本。两次最终确认也保留独立尝试。退化候选为官方执行成功的 `ok`，不伪标 failed；本批没有执行失败或超时。旧批本身包含 8 次候选构造、13 次 P2 E0；不含历史 seed 生产调用。

## 时间与缺口

- 所有 `solver_wall_seconds=null`：没有从图冷启动完整求解计时，历史 seed 搜索也未计入；不使用整批 2.831822542 秒冒充逐例 solver wall。
- `evaluation_wall_seconds` 保留每次 `subprocess.run` 前后的原始浮点秒数，含官方进程启动/等待；不含此前计划落盘与预留，以及事后结果压缩。
- 共享索引/局部构造秒数与整批窗口单列 parameters；索引被四个策略共享，不能按四份总计。3 基线 + 8 候选 + 2 确认共用 13 次/180 秒预算，120 秒后不再启动，每次 CLI 限 30 秒；这些是旧预算，不授权再次执行。
- 每次 UTC 起止、CPU 型号、RAM、线程数、峰值 RSS 未在旧收据记录，保留 null 和具体原因。只记录实际存在的批 T0，不用当前机器、Git 时间或文件 mtime 补造。
- 原始上游 seed 参数/完整生产成本未在本批复记；固定计划字节来源可查，不将其表示为无成本输入。未附本批不存在的官方单核分母，接收方可按冻结身份匹配已核分母。

## 复现导出与只读预检

以下命令不导入或运行 solver/evaluator，仅读取历史文件/Git 字节，输出新 feed。需要旧固定提交可由本地 Git 读取。输出路径须不存在；不要覆盖已交付快照。

```sh
python3 src/q2_nikolastarx/export_board.py results/a/q2-nikolastarx/board-export-20260924/board-feed-NEW.json
python3 src/benchmark_board/protocol.py results/a/q2-nikolastarx/board-export-20260924/board-feed-NEW.json --submission
```

本次实际预检使用 `board-feed-20260924T132237Z-history13.json`，退出码 0。预检只在临时目录核对，不写中央库。协议仍由成绩台维护者单写；导出器不新增接收格式。
