# Stage K：100 官方图 × k4 受限验证准备

负责人：@yuanzhifang30-sudo；原 session `yuanzhifang30-sudo/s-0e91469d5b284a0aaf7aca42c456233c`（continue）。实际运行监督人由 `--producer-session` 记录。

分支：`codex/q1-unified-pacing-20260925`；沟通 [Issue #98](https://github.com/huaweibei123/huaweicup2026/issues/98)。

1. **任务目标**：固定 Stage K solver `08e5cbf96c57bbfb603ec9661ee591e2adb8c26f`，在 100 个官方用例各跑一次 k4 冷求解，与队长 `a0537aeb` 完整 500 固定原件同图/配置/官方 E0/实际新计划字节比较。官方 E0 Makespan 为质量；新进程从启动到输出、E1 子进程收尾的外层墙钟为效率。旧 E0 原件只作精确匹配复用，不复用旧 solver 时间。
2. **输入文件**：`--graph-dir` 指向只读原始 `case_001.json`…`case_100.json`，与固定 `docs/a/source-manifest.json` 100 条 SHA-256 逐一核对。`--reuse-feed`/`--reuse-commit` 明确指向队长批准的 `9c5f87548cc7588465a638e032993969b5cac891`/`results/a/q1-unified-v4-full500-20260925-s59/20260924T1952Z-s59ee/board-feed-500.json`，feed SHA-256 `4cd79828999ad56dc00d34a79cc0dcd921fff783e5aaf793b0c84924b0f10764`。原件可由固定 Git object 读取，不将大包复制进源码。
3. **输出要求**：`python -m src.q1_yuanzhifang_stage_k.benchmark_k --graph-dir GRAPH_DIR --output RESULTS_DIR --reuse-feed FEED_PATH --reuse-commit 9c5f... --start-token STAGE-K-100K4-ONEWORKER-START --producer-session ACTUAL_SESSION`；只读准备检查用 `--preflight` 且省去 START。默认新 run 目录 `results/a/q1-yuanzhifang-stage-k/stage-k-100k4-oneworker-20260925/run`，与取消的旧准备隔离。每格独立两字段 plan、diagnostics、在线事件、stdout/stderr、run.json、真实或匹配复用 E0 的 result/trace；新 E0 才有本轮 log。批次 manifest/receipt 保留未启动、失败、超时及 E1 尝试/确认/未知分类。`export_k` 仅从这些原件导出 submission-v1，不调用评分器；未得到 E0 的格为 `not_run`/失败，Makespan 与均值均不填。
4. **限制条件**：父 P1 监督会话 START 后才运行；≤100 cold solver、≤700 E1 接口尝试（每格至多 7，失败缺诊断按 7 计）、≤8 新外部 E0、0 retry/E2；**1** 个受 Job Object 管理的 Windows cell worker，每 solver ≤120s、每 E0 ≤180s、全批 2400s。启动时可用物理 RAM≥1.5 GiB；每个 solver/E0 owned Job 强制 aggregate committed memory ≤1 GiB，设置失败即停止。100 图和 solver/E1/官方源码/配置/固定 feed 身份先验核对。超时只清理本批 owned Job，确认 active=0；监督/身份错误阻止未开始格。E0 复用仅在 case、k4、图/config/整套官方源码 hash、实际新 plan 原始 SHA、固定 feed 及 raw plan/result/trace/run SHA 与内容匹配时允许；旧档无 E0 log 须明确缺项，旧 E0 wall 单列为来源记录且本轮 E0 calls=0。
5. **验收标准**：准备期只做语法、来源和单份固定原件只读/临时复制预检，0 真实图 solver、0 Task compiler、0 E0/E1。正式批次需每格核原始计划与完整 E0 result/trace，按 board submission-v1 协议本地与固定提交验收；不能用 audit rows 或仅指标表冒充 raw。只对已成功 E0 的格报告实际成绩；100/k4 可评估后才谈覆盖与均值。
6. **截止时间**：2026-09-25，Asia/Shanghai；本提交是可执行准备，实际 START 与预算协调由父 P1 会话负责。

## 交付记录

实际命令：见提交报告；准备期 0 评分。固定源 feed 加载确认为 100 个 k4 合法行，001 原 plan/result/trace/run 字节和关联 SHA 预检通过。

代码提交与输入版本：solver 固定 `08e5cbf96c57bbfb603ec9661ee591e2adb8c26f`；runner/exporter SHA 交付时填写。

结果与图表：准备代码及预检记录，暂无 100/k4 新方案或 E0 成绩。

结论及限制：队长完整 500 在 9c5 固定提交，不把其速度或 plan 质量自动赋予 Stage K；预备 runner 限时可能导致 100 格中未评估格。队长原档未归档每格 E0 log，复用时不补造。

未验证项：Windows Job 真实多进程超时行为在本批、100 图冷启动求解耗时、H/J 新增候选触发分布、实际复用命中和新增 E0 成绩。无正式 START。

### 单 worker 修订（未启动）

旧 `8acaaa9ac9896aed30f8501c72810798c1d8ac09` 双 worker 版在 START 前因可用 RAM 低于 2 GiB 取消，**0 solver/E0/E1**。父独立核验 CIM 1,710,186,496 B 与 GlobalMemoryStatusEx 1,764,724,736 B，未发现本线遗留进程；未忙等或重试。此修订降低并发并用 Job Object 的 `JOB_OBJECT_LIMIT_JOB_MEMORY` 限制整棵 owned 进程树的提交内存，不放宽调用/时间预算。旧取消记录不覆盖，新 run id/START token 明确区分。

PR：父会话统一处理；本线不创建 PR。
