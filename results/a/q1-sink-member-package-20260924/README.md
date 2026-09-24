# P1 sink-peel：成员八格固定候选包（准备完成，尚未执行）

本包仅交成绩台研发接收与分配 owner `s-7c98…` 安排 LYX / farmer 等实际执行者。
准备者没有启动任何求解或E0，也没有向成员发信。源码字节核对、参考原件复制和
合成子进程控制测试不构成真实图评分。执行人须先取得 owner 的明确批次/资源窗口。

## 固定任务六字段

1. **目标**：检验粗 sink-exclusive suffix waves 对另外8个已静态识别激活的
   单连通真实图是否改善官方P1 Makespan；完整保留变差/失败。收益不以波数或零spill代替。
2. **输入**：`manifest.json` 固定图`005,047,064,069,075,082,085,086`，全部k4。
   原ZIP/config/10份官方源码只读，运行前后逐字节哈希核对；所选图在ZIP中的字节也逐个核对。
   算法 `src/q1/sink_peel.py` 固定`d89a6cbf1e292f2abc36b4fef89590d16ccb1ab2`，
   及其 bounded_tasks/tree_frontier/component_pack 与该提交原字节一致。
3. **产物**：每格独立plan/result/trace/official.log/诊断/stdout/stderr/run.json，
   批次batch/preflight/postflight、完整失败/未执行行、board-feed.json与comparison.json。
   成功result/trace仅无损gzip，失败/部分文件原样保留；每个字节引用有SHA256。
4. **边界**：最多8次完整solver+8次独立E0；1worker顺序执行；每solver30秒/E060秒，
   整批600秒调度/执行deadline（包括源码核对与ZIP准备）。剩余总预算不足时单进程期限缩短；
   停止后的直接子进程kill/wait最多10秒宽限和最终字节复查可使收尾稍超600秒。
   0重试/E1/E2/GPU/Colab；不可改参数、加核数或追加候选。第一次单格失败/超时、
   源码不符或监督错误停止派发，其余明确not_run。
5. **验收**：所有原件及调用账真实完整，直接子进程已回收；比较Makespan、额外DDR/spill、
   Task/波数、完整求解墙钟和独立E0墙钟。schema/原件准入与独立复跑、算法科学验收分开。
   未实际运行不能预填eligible或把预制manifest当成绩feed。
6. **截止/交接**：由owner安排成员执行窗口；本准备任务到固定包交付结束。
   实际执行固定此包提交，不从浮动main或“latest”运行。执行完成交owner统一接收。

参数固定：max_rounds64/max_sinks64；fallback factor4/trigger4096/chunk1024。
每个solver调用内部包含一次完整bounded04构造，该成本已计入同一进程端到端墙钟。
无在线评分、模型训练或针对当前图的隐藏预计算。ZIP物化/源码校验属于批次准备，另计；
图JSON读取、构造、结构验证、计划/诊断落盘、Python启动及退出均属于solver wall。

## Windows / macOS / Linux 最小命令

成员在保存自己工作后，使用 owner 提供的本包完整提交建立独立worktree，不覆盖原任务。
下面命令在新工作区根执行；`FULL_PACKAGE_SHA`、session、runtime、run-id和并发说明必须替换成实际值。
`FULL_PACKAGE_SHA` 是本包最终提交，运行器要求HEAD精确匹配。

```text
uv sync --locked
uv run python -B src/q1_benchmarks/sink_member_batch.py preflight
uv run python -B src/q1_benchmarks/sink_member_batch.py run --run-id MEMBER-YYYYMMDDTHHMMZ-sink8 --expected-runner-commit FULL_PACKAGE_SHA --producer-session login/s-32hexuuid --runtime-id member-windows-py312 --concurrency-context "actual owner-agreed resource window and other workloads" --execute-authorized
uv run python -B src/q1_benchmarks/sink_member_batch.py export --run-id MEMBER-YYYYMMDDTHHMMZ-sink8
```

没有授权窗口仅运行preflight；它不import算法或评估器。`run`不能重用已有run目录。
`--execute-authorized`用于防误触，不替代owner的派发授权。发生中断先保留目录与进程状态，
向owner交现有账，不能删目录重跑或增加retry。批次未正常收尾时export拒绝，交owner判断恢复证据。

本runner没有`os.killpg`或Unix信号依赖，使用`Popen.wait(timeout)`、`kill()`、`wait()`
回收**直接子进程**，这些API在Windows可用。静态检查固定solver/官方源码没有启动子进程的代码；
不承诺任意未来子进程树清理。每次启动的完整Python命令与真实UTC/墙钟、exit_code、PID、
cleanup_confirmed记录在run.json。原始stdout/stderr不改写，若失败traceback含个人路径，
发布前由生产者保全原件并显式衍生脱敏副本，不应悄悄覆盖原始证据。

准备期仅在macOS / Python3.12.13测过合成控制器：成功退出、非零退出、超时kill+wait、
启动失败4项。没有真实图构造/E0；**没有实际Windows执行验证**，也未预先声称8格会成功。
Windows成员可先运行`self-test`验证本机控制器，再按已授权窗口执行；self-test仅4个合成小进程。
CPU/RAM/平台/Python/锁文件哈希会现场记录；未采样线程数和peak RSS明确null。
本包没有硬内存限额或资源独占保证，资源窗口由owner安排；不得把1worker当整机无其他任务。

## 现有证据与分母复用

`reference-index.json`及`references/`已复制并核对同图bounded04与官方单核结果原始压缩字节，
来源固定`ad8903ba8c7bf0dcb96913f5ed23f9ab0bb8ddf9`，不需要成员重新跑参考值。
真实k4构造与官方singlecore分母不同，不以任意旧P1 k1方案冒充分母。

048/071已经测过，**不在8格执行矩阵**。本分支祖先含原计划/result/run；manifest引用固定
`869393453dc1e0e3ae7c119c0ba3f1d66a35f315`下两格原件，Makespan分别116460/12078。
未来可把同源码/参数的这2格与8个新attempt作10图研究汇总，但须保留不同机器、批次和计时差异；
不能算作10个新评估，不能冒充全100图结果，更不能混入其它算法历史best。

## 成绩台交付

导出路径：`results/a/q1-sink-member-runs/<run-id>/board-feed.json`。
导出器填写真实成员session、机器、固定runner/solver来源、参数/预算、每次启动调用数、
未知项原因及官方单核原件引用；不会调用solver或任何评价器。所有相对原件均在同一最终Git提交。

若成员已有成绩台协议代码，可在根执行：

```text
python src/benchmark_board/protocol.py results/a/q1-sink-member-runs/RUN_ID/board-feed.json --submission
```

本分支保留算法历史基线，未复制中央网站代码。没有protocol.py时，owner可用其现有固定
协议checkout运行`protocol.py <feed相对路径> --repo <成员结果checkout> --commit <结果完整SHA> --submission`，
不需要为预检重跑实验。最终接收仍由owner完成。

成员要显式保全被`.gitignore`忽略的`official.log`（只force-add本次明确日志）；提交后逐项
核验feed引用可`git show <结果SHA>:<path>`读取且哈希相同。报告包含失败和not_run，不能只上交好格。
