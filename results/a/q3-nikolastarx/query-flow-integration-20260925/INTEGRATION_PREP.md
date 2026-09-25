# 071/K5 统一入口零评分准备

本目录仅是待审提案。`integration-manifest.json` 当前 `execution_authorized=false`，runner 与 supervisor 在执行前会拒绝。新 E0 许可为 0；没有启动 runner、solver、Task、Step、constructor、官方评价或受控子进程。

冻结求解源码基点为 `c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43`，当前实际 HEAD 也是该提交。未来交付 HEAD 可前进，但启动前必须证明 c960 仍为祖先、`git diff c960 -- src/q3` 为空，并核 manifest 全部源文件集合与逐字节 SHA。manifest 列出 `src/q3` 全树 80 个文件、官方 code 10 个文件及原始 `case_071.json`/`config.txt`，共 92 个逐文件 SHA-256；还核本目录 runner、supervisor 与 `resource_supervisor.py` 身份控制依赖的 SHA。启动回执分别记录实际 delivery HEAD、冻结 solver commit 和 `query_flow_solve.py` SHA。输出仅 `results/a/q3-nikolastarx/query-flow-integration-20260925/run/`，目前不存在。代码、输入、预算、命令及资源规则须整体重审后才可授权；不得把旧 R2 预算转给本计划。

`integration_runner.py` 在同一 Python 进程内通过 `runpy` 执行冻结 `src.q3.query_flow_solve` CLI，保留原构造与方案落盘。官方 P3/P2 函数入口包裹在调用前写外层账，分别最多 4/2 次，每次 `SIGALRM` 90 秒。官方异常与超时转为 `BaseException` 派生的终止异常，不能被候选的 `EvaluationValidationError` 分支吞掉；不重试。runner 从入口到图读取、构造、评分、输出落盘计外层墙钟。

`integration_supervisor.py` 只启动该一个 runner 进程组，整个窗口 600 秒，每秒采样已核实组 RSS、memory pressure、物理 free、swap used/free、磁盘余量和其他 scorer。提议的启动/运行硬门：pressure=1、其他 scorer=0、disk free≥10GiB；运行时本组 RSS>2GiB 或 swap used 相对 T0 上升>256MiB 则停止。物理 free 与 swap free 只观测，不沿用旧 6GiB 门槛。外监督计时覆盖启动前采样至结束采样；1 秒采样不保证捕获瞬时峰值，也不证明 OS 冷缓存。

早期 `test_integration_mock.py` 一轮原件覆盖 4P3/2P2 边界、首个官方异常中止和资源门；它调用的是 `identity_guard.finish_exited`，**不能证明当前 integration supervisor 的终态实现**。本轮新增并只执行一次 `test_terminal_zombie_mock.py`，原件 `terminal-zombie-mock-results.json` 与 `.stdout.txt`：已退出父进程仍有 zombie `ps` 行时成功且零信号，已核遗留组仅对该组发模拟信号并标失败，PID 复用/未知身份零信号，已有失败状态保留。新 supervisor 的终态函数仅忽略**已由 waitid 确认退出的父行**，其余组继续要求历史已核身份与当前组成员核验。静态审查确认循环在活父采样前查退出、采样后再查一次；若父进程短到初次 libproc 身份读不到，先检查 `waitid` 并在已退出时走终态分支。这个短命入口修订在本轮 mock 后，未再执行脚本。若身份仍不可用但子进程仍活，则拒绝未知组信号并保留失败，需人工处理。完整 `main()` 调度、真实 macOS `ps`/libproc 竞态、实际构造/评价质量、真实资源峰值和冷缓存仍未验证。单次终态组检查与 `killpg` 间仍有无法原子消除的 OS 竞态。

固定 SHA-256：runner `523691108f5544aa63e042f7e4b9fff1c68bbbfc54b921d25d8c424219af3371`；supervisor `aaefef1e9507e4de322e432e72431c3aa1af308a1621d6f8c65a9e78c96db7ab`；manifest `7074534e4ac2afed264b8a75bad078be42ac0850d9cca70205fed75e58e7e1ee`；身份控制器 `9589577c7f916f3b759fe8508e8cc8304820e810de56ad767264f83a2e72b1d6`。
