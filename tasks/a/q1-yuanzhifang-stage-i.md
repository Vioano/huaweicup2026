# Stage I：五格前瞻 pilot 准备

负责人：yuanzhifang30-sudo，session `s-0e91469d5b284a0aaf7aca42c456233c`，Issue #98。本会话 fork 已暴露 051/084/008 的前期机制信息；这五格是诊断 pilot，不称盲测或全量均值。

1. **任务目标**：用同一固定 P1 solver `397e7ca0b680f50336e4dd4eefb14831015107d8`，在 051/k5、084/k2、084/k4、084/k5、008/k5 各冷运行一次，再对合法两字段计划各作一次未修改 E0 外部复评。051/k5 可与既有 H 固定成功 `1c9b654223b663f6e624fc413913c076c843ed56` 比较；其余旧基线由队长给固定原件，pilot 不重跑。
2. **输入文件**：`--graph-dir` 指向工作树外既有原始 `case_*.json` 目录；固定仓库相对配置与官方代码。启动前核源码哈希、完整 solver 提交、三图 SHA-256、官方与配置 SHA、环境和可用磁盘。原始图不复制、不改动；没有 case ID 参与 solver 选择，只用于固定 pilot 列表。
3. **输出要求**：`results/a/q1-yuanzhifang-stage-i/stage-i-20260925/run/` 每格独立保存两字段方案、诊断、在线事件、完整 lossless gzip E0 result/trace、E0 log、两个进程 stdout/stderr、run.json；批次有 manifest 和 receipt。外层冷 solver 墙钟自进程启动至输出、Job 清理和退出；E0 另计。`baseline/` 中 008/051/084 的 `run.json` 和 `result.json.gz` 从固定 `0b47d802cdd0bfe7011017c8098c1c0917b2c959` 逐字节复制；导出时再核原件、图/config/官方身份及分母，不重跑。`export_i.py` 只读原件导出 submission-v1 feed；先作本地 protocol eligible 预检，发布固定结果提交后再 `--commit FULL_SHA` 预检。失败、超时、缺口均保留，不用摘要代替原件。
4. **限制条件**：两个并发 cell worker；最多 5 solver、25 在线 E1 接口尝试、5 外部 E0、0 E2、0 重试。solver/E0 各 180 秒，全批 1200 秒全局 deadline。单进程先在 gate 等待，加入 Windows Job 后才运行；超时 TerminateJobObject，并核 ActiveProcesses 为零再关闭 Job；若指派 Job 失败，只终止仍在 gate 的本批父进程。监督/身份故障停止派发尚未开始的格。外部真实运行等待父 P1 监督会话在固定预算与同机协调下发 START（用户已授权持续实验，不是跨账号重新审批），由实际执行会话传 `--start-token STAGE-I-20260925-START --producer-session LOGIN/s-UUID`。启动前人工核主机其他批次、内存和空间；共享主机并发墙钟标明，不冒充独占性能。
5. **验收标准**：准备期只核源、命令、语法、Job 清理 dummy（1 个 dummy parent 加 1 个 dummy descendant），0 真实图 solver/Task 编译/E0/E1/E2。pilot 执行后逐格核两字段计划、E0 原件、图/config/官方哈希、在线尝试账与预算、Job 退出、local/fixed-Git submission-v1 eligible；不把 E1 在线选择当 E0 保证。008 保留已知退化线索，所有失败/退化如实交回。
6. **截止时间**：准备交付为 20 分钟软目标；正式 START、1200 秒批次及后续验收由队长另定。

## 冻结命令

只读预检：`python -m src.q1_yuanzhifang.benchmark_i --graph-dir GRAPH_DIR --preflight`。

获父 P1 监督会话 START 后：`python -m src.q1_yuanzhifang.benchmark_i --graph-dir GRAPH_DIR --start-token STAGE-I-20260925-START --producer-session LOGIN/s-UUID`。

导出：`python -m src.q1_yuanzhifang.export_i --feed results/a/q1-yuanzhifang-stage-i/stage-i-20260925/board-feed.json`。由同一仓库固定的 `src/benchmark_board/protocol.py` 运行 `python src/benchmark_board/protocol.py FEED --submission`，提交原件后加 `--commit FULL_SHA` 再验。若 protocol 不在此稀疏工作树，队长按固定主库提交提供只读执行路径；不把预检失败改称 eligible。

本次尚无 START，未执行上述真实命令。已有 dummy Job 测试在工作树外临时目录完成：父进程 0.5 秒超时，Job 关闭后子进程 PID 不再存在；这只验证清理路径，不证明 E1/官方评分成功。
