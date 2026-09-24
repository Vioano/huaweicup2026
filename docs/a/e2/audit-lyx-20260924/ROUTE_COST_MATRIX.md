# E2 调用路由与官方评价成本：LYX 静态检查点

结论：固定实现的公开单候选接口最多进入一次完整后备评价；P1 是完整 E1，P2/P3 是对应冻结 E0。冷 native 准备后失败，可能执行两轮准备链，但不是两次完整 E0。`native_enabled=True` 没有禁止回退的含义。派发后的超时、进程异常和取消通常无法确定完整评价实际是否进入，必须保留 unknown。

## 范围与实际执行

- 负责人：`lyx0217/s-89ad75751f054b6b9929e42d899246be`，Codex / Windows；同机子 Agent 分读 P1、P2/P3、pool/CLI，主 Agent 汇总核对。这是静态审阅，不是多机独立实验。
- 任务卡：`64d2c39f6904d4548c96d601ff59dda4a61b3726:tasks/a/E2-ROUTE-COST-AUDIT-LYX.md`；[派发](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805254419)、[接手](https://github.com/huaweibei123/huaweicup2026/issues/15#issuecomment-5805307559)。
- 输入代码：**603b0741e21c449d3db652ebd67c94f2dc014cc9**，下文代码行号全部属于此版本。报告分支 `codex/e2-route-cost-audit-lyx0217` 从 main `1b19960af15fce14c84e8e23f2ea6cff6bd910d0` 建立，没有合入算法分支。旧 FAST/PR20 保留。
- 首检查点把准备时间也计入：2026-09-24 **08:31:14 至最晚09:01:14，Asia/Taipei**。截止不自动延长；不以“还有未读文件”为由启动实验。
- 实际 E0/E1/E2 评价、原生构建、worker/测试启动、依赖安装均 **0**。没有 import 或执行被审源码，包括 `--help`。读取命令为 `git show <SHA>:<path>`、`git ls-tree`；冻结文件另经 `git cat-file blob` 原始字节与 .NET SHA256 核对。只写本目录两个报告文件。
- Actions 按免费策略停用；本地只检查文档、JSON、引用与 diff。未运行算法测试，未验证 DLL/ABI、性能或官方结果等价性。静态检查点不等于 E2 终验。

## 计数定义

本表是**已读固定调用链、一次候选调用/派发、无外部重试**的条件上界，不是本轮实测调用数。假定正常 JSON 形状的数据、未猴子补丁的加载器/依赖及预期原生库；任意带执行副作用的 Python 对象、被替换 DLL 或外部重入不在证明范围。

- `E0`：进入未改动的完整官方 `evaluate_scene_a / evaluate_scene_b / evaluate_problem_3` 函数及其正常冻结依赖所组成的 oracle 路径。加载模块、读配置、参数绑定失败、准备 Step1/2/3 都不算完整 E0。
- `E1`：进入完整 E1 全局评价路径。P1 E2 API 走 `batch.py → _scene_a.py`；P1 官方格式 CLI 走 `problem1.py → runtime.evaluate_scene_a`，函数体来自官方，但 task builder/Step3 依赖已改，仍列 E1，不能算纯 oracle 验证。该 CLI 另注“官方函数体入口最多1”，不能与 E1 再加一次。
- `prep`：上层进入一次 Task/core 构建管线，不是完整评价，也不是其 CPU/秒成本。P1 管线至多逐 Task 调用 Step1、Step2、prepare-Step3；P2/P3 至多逐非空核调用这些阶段。部分失败可只完成部分阶段，表内是至多轮数，不能推导实际工作为0。
- `max` 是静态可达上界；`actual` 在中断后可为 unknown，即使 max=1。成功完整结果足以说明对应一次完整评价完成；单独 route 字符串、累计 fallback_calls/full_calls 或外部 `started` 标志不足以证明函数体已进入。
- caller、worker、包装器、函数内部 helper 是同一调用链，不逐层重复收费。E0 与 E1 互斥路由计数；`prep` 是另一个维度，不能加成“E0 次数”。

## 单候选矩阵

以下 ID 与 `route-costs.json` 一致。P23 行对 P2、P3 **各自**成立，分别进入自己的完整函数，不串行调用两个问题。`≤` 包含参数/验证提前失败；成功 full/fallback 的对应完整评价数为1。每行都不提供运行时秒数保证。

| ID | problem / 条件 | 返回或后端 | E0 max | E1 max | prep max / 缓存行为 | 证据 |
| --- | --- | --- | ---: | ---: | --- | --- |
| P1-N-COLD | 1 / score，native miss 成功 | native | 0 | 0 | 1；构建、pack、验证并重放，成功后才准入 | E01,E02,E03,E04 |
| P1-N-HIT | 1 / score，native hit 成功 | native | 0 | 0 | 0；仍校验参数/顺序并重新重放，不缓存分数 | E01,E04 |
| P1-DISABLED | 1 / score，native_enabled=False | e1_fallback | 0 | 1 | ≤1；E1 的 Task cache 已关 | E01,E02,E03 |
| P1-EARLY-FB | 1 / native 在 builder 前失败 | e1_fallback 或 error | 0 | 1 | ≤1；仅后备准备，输入错误也可能有代价 | E01,E02 |
| P1-COLD-FB | 1 / native 冷准备中或之后失败 | e1_fallback 或 error | 0 | 1 | ≤2；冷准备部分/全部 + E1 重建，含 P1 延迟加载 DLL 失败 | E01,E02,E03,E04 |
| P1-HIT-FB | 1 / 命中后 native 失败 | e1_fallback 或 error | 0 | 1 | ≤1；E1 重建，旧 E2 缓存不自动驱逐 | E01,E02,E04 |
| P1-FULL | 1 / full=True，任意 native 开关 | e1_full 或 error | 0 | 1 | ≤1；绕过 E2 lookup，仍构造完整 E1 结果 | E01,E02,E05 |
| P23-N-COLD | 2/3 / score，native miss 成功 | native | 0 | 0 | 1；官方 builder/validate_execution + pack + replay | E06,E07,E08 |
| P23-N-HIT | 2/3 / score，native hit 成功 | native | 0 | 0 | 0；仍查库、验参数并重新 replay | E06,E08 |
| P23-DISABLED | 2/3 / score，native_enabled=False | e0_fallback 或 error | 1 | 0 | ≤1；完整 E0 重新构建，非“禁用所有评价” | E06,E09,E10 |
| P23-EARLY-FB | 2/3 / config keys、local install、DLL/ABI、参数/容器前置失败 | e0_fallback 或 error | 1 | 0 | ≤1；native 尚未构建，E0 可再验证/构建 | E06,E07,E08,E09,E10 |
| P23-COLD-FB | 2/3 / builder、执行验证、pack、replay 或返回构造晚期异常 | e0_fallback 或 error | 1 | 0 | ≤2；fast 准备 + 冻结 E0 准备，不是2次完整E0 | E06,E08,E09,E10 |
| P23-HIT-FB | 2/3 / 命中后 native 异常 | e0_fallback 或 error | 1 | 0 | ≤1；E0 不消费 E2 编译缓存 | E06,E09,E10 |
| P23-FULL | 2/3 / full=True，任意 native 开关 | e0_full 或 error | 1 | 0 | ≤1；绕过 E2 lookup，完整结果附在 result | E06,E09,E10 |
| P23-BIND-REJECT | 2/3 / 可证明 fn 参数绑定失败、函数体未进入 | e0_full/e0_fallback + error | 0 | 0 | 0（本行只指完整入口前绑定失败）；route/counter 可已增加 | E06 |
| PRIVATE-NATIVE | 1/2/3 / 私有 _native_score 直接调用，不经过 evaluate_record | native 或抛出异常 | 0 | 0 | ≤1；P23 debug 强制冷准备且不准入 | E01,E06,E08,E15 |
| P1-CLI | 1 / 官方格式 CLI | 完整 E1 CLI | 0 | 1 | ≤1；官方函数体入口≤1但依赖已改，不算第二次评价 | E11,E12,E03 |
| P23-CLI | 2/3 / 官方格式 CLI | execv 对应官方 CLI | 1 | 0 | ≤1；参数/输入/config 可在完整入口前拒绝 | E12,E13,E09,E10 |

`PRIVATE-NATIVE` 只是已读私有调用事实，不是建议绕过公开接口或授权的预算方案；它不提供正式稳定的“native-only”公共契约。P1 API 顶层必需参数绑定失败发生在 `evaluate_record` 函数体之前，整次请求完整评价数可证为0；不要把它与已经进入 evaluator 后产生的 error 混淆。

`P23-BIND-REJECT` 的0需要实际调用点/异常前置性证据，不能仅凭异常类型名推断：完整函数内部也可能抛 TypeError。P23 `full_calls/fallback_calls` 在调用表达式之前增加；因此它们是路径尝试数，不能直接作为完整 E0 started 账本。

## pool、started 与中断费用

| ID | 事件 | 可确定上界与不能确定的实际费用 | 证据 |
| --- | --- | --- | --- |
| POOL-PRE-DISPATCH | 当前 chunk 尚未发送任何候选就 startup 失败 | 当前 chunk 的候选完整 E0/E1 为0；已完成的以前 chunk 仍须计费，worker 加载/初始化 CPU 不能记0 | E14 |
| POOL-SEND-UNKNOWN | connection.send 后、或发送失败无法证明子端是否收到 | 每候选 P1 E1≤1、P23 E0≤1；实际进入/完成数 unknown，不能以 caller 未登记 active 推定0 | E14 |
| POOL-TIMEOUT | 已派发后超时 | 同一上界；实际完整评价/准备进度 unknown。先判超时再读已就绪响应，可能已经完成 | E14 |
| POOL-WORKER-ERROR | 崩溃、EOF、异常/不匹配响应 | 同一上界；完整评价实际数、CPU、结果 unknown；_failure 缺少阶段证据 | E14 |
| POOL-CANCEL | close、generator close、取消竞争 | active 请求可能未开始/进行/完成；同 chunk 全处理后才顺序 yield，已 yield 数不是已执行数 | E14 |
| POOL-RECYCLE | timeout/崩溃后重建，或 max_tasks/RSS 回收 | pool 不自动重试本候选；新 worker 为后续候选服务并丢失缓存。外部重试总成本无本实现上界 | E14 |

公开 evaluator/pool **没有**逐候选或 E0/E1 函数体级的 started 协议、fallback 许可回调、预算令牌、跨重试幂等账本。worker `ready` 只表示初始化完成；`active` 是派发记录。caller 可在派发前拒绝整个请求，但不能既允许 native 又要求“回退前先询问”。`full=True` 必须预留对应完整评价；`native_enabled=False` 强制后备；`True` 仍要覆盖自动回退的最坏分支。未来设计可采用阶段与预算令牌，但本审计没有实现或验证它。

拒绝/异常不等于成功，`invalid` 仅来自明确的官方验证分类；资源、死锁、max_iter 等仍可能是 error。BaseException、硬崩溃和外部取消不受 `except Exception` 保证。中断后不因没有最终记录就退还“尚未使用”的费用；需独立、持久阶段证据再结算。一次请求的静态完整评价上界仍可为1，与其 actual=unknown 并不矛盾。

## 缓存、时间与脚本账本

- P1 key 是有序原始 mapping、bandwidth、capacity；schedule/waits 不入 key，但每次重新验证核心顺序及依赖并 replay。E1 内层缓存明确为0；native 已准备后失败会重新准备。命中也非“免费”。P23 key 包含完整有序 plan、bandwidth、capacity、P3 cache bandwidth；delay/max_iter/cache capacity 每次应用。full 不复用这些编译缓存。冷失败不保证完全无缓存变化：若失败发生在准入后的结果构造，条目可能已经保存；命中后失败不自动驱逐。[E01,E02,E06,E08]
- 上述 prep 轮数只数上层构建管线。P1 的 T 个 Task、P23 的 K 个非空核决定内部工作量；最多两轮不等于两次完整 E0，也不等于两倍确定秒数。未给官方 helper 内部递归调用、内存峰值或墙钟的常数上界。[E03,E09,E10]
- `cli.py:25` 在 argparse 之后开始计时，`25–45` 覆盖读图/config、worker、IPC、评分、写出与回收，**排除 Python 启动/import**。不是官方目标要求的从进程启动起的完整 wall。`pool.py:204` 同步 send 期间没有独立超时监控；其 timeout 不能说成严格进程硬截止。[E14,E16]
- 辅助脚本有局部 `started` 标志，不等于公开接口已经具备阶段协议。`evidence_b.py:64–68` 先保存 started/reserved=1 再调用 full；标记本身不是进入函数体的原子证明。其私有 debug 调用不回退，但完整脚本随后还显式做 E0，不能把局部0推广为全脚本0。[E15]
- `resources_b.py:78–93` native 批预留0，子进程仍可能自动回退；事后 `route` 断言无法阻止已发生的 E0。`verify_b.py:92–97` 在收到 fallback 记录后才记账，其111–115另先跑完整pool批次再断言native，这一段不追加fallback账本。它们不构成通用事前预算门禁；本次没有运行或修改。[E17,E18]
- `benchmark.py:140–146` 全池 truth、`workflow_probe.py:50` 最终确认各有显式完整 E0。属于调用方额外工作，不能隐藏在单候选 native=0 的结论中。其所有参数化分支/整个脚本总量未穷尽审计，整次任意脚本/外部重试成本标 unknown。[E19]

## 固定证据索引与阅读清单

链接均固定到输入 SHA。索引中的所有行号均为函数/调用点定位，不表示只有被链接一行才是依据。

| ID | 固定文件、函数与已读范围 |
| --- | --- |
| E01 | [engine.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/engine.py#L66)：全文；__init__ 66–83、_native_score 96–158、evaluate_record 160–192、batch 194–197 |
| E02 | [batch.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/src/eval_exact/batch.py#L43)：全文；P1Evaluator 43–69、_build_tasks 71–109、evaluate 111–132、evaluate_record 154–171 |
| E03 | [problem1.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/src/eval_exact/problem1.py#L114)：全文；builder 114–262、逐Task Step1/2/3 165,234–243、patched runtime 265–285 |
| E04 | [_native.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/_native.py#L116)：全文；pack 41–74、validate_orders 77–105、get_lib 108–114、score 116–143 |
| E05 | [_scene_a.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/src/eval_exact/_scene_a.py#L13)：全文，完整派生E1函数13–354，无再转完整E0 |
| E06 | [scene_b.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/scene_b.py#L124)：全文；两私有bundle 45–53、native 61–122、full/fallback/分类124–164 |
| E07 | [_official_b.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/_official_b.py#L11) 与 [_local_b.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/_local_b.py#L12)：全文；load_bundle 11–36 / read_config 39–57；install 12–69只改fast副本 |
| E08 | [_native_b.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/_native_b.py#L102)：全文；pack 30–98、库/ABI 102–114、score 117–158 |
| E09 | [冻结P2](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/data/raw/a/official/code/multicore_cut_evaluate_problem_2.py#L68)：子Agent读取调用链；helper imports 15–23、builder 68,245–266、完整evaluate_scene_b；无内部完整P1调用 |
| E10 | [冻结P3](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/data/raw/a/official/code/multicore_cut_evaluate_problem_3.py#L292)：子Agent读取调用链；helper imports 13–19、builder 76,253–274、完整evaluate_problem_3 292起；无内部完整P2/P1调用 |
| E11 | [P1 CLI](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/src/eval_exact/cli.py#L41)：全文；_run 13–64、入口41–48、main 67–73 |
| E12 | [官方格式包装器](https://github.com/huaweibei123/huaweicup2026/tree/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search)：三个 multicore_cut_evaluate_problem_*.py 与 _full_cli.py 全文，P1转E1；_full_cli.main 7–14只execv一次 |
| E13 | [contest_io.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/data/raw/a/official/code/contest_io.py#L197)：官方CLI路由段197–265；输入/config在206–224，P2/P3完整入口237/246 |
| E14 | [pool.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/pool.py#L31)：全文；worker31–66、启动143–167、failure169–172、派发196–209、超时/响应210–243、yield/取消244–253 |
| E15 | [evidence_b.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/evidence_b.py#L46)：1–86，debug49、显式E0/ledger64–70 |
| E16 | [cli.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/cli.py#L25)：全文；没有 __main__.py 包入口，真实入口49–50 |
| E17 | [resources_b.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/resources_b.py#L78)：相关child/pool及ledger链；主Agent复核1–106 |
| E18 | [verify_b.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/verify_b.py#L92)：相关评价/ledger调用链；主Agent复核65–106，子Agent补核111–120 |
| E19 | [benchmark.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/benchmark.py#L140) 与 [workflow_probe.py](https://github.com/huaweibei123/huaweicup2026/blob/603b0741e21c449d3db652ebd67c94f2dc014cc9/research/a/e2_search/workflow_probe.py#L50)：主Agent只读前者115–159、后者1–78，显式额外oracle入口；未穷尽整个脚本 |

另已全文读 `P23_HANDOFF.md`、`research/a/e2_search/__init__.py`、`src/eval_exact/_official.py`；后者 `35–50,68–126` 的加载/哈希保护不等于一次完整评价。相关冻结 P1、manifest 和 export 链由同机子 Agent 读取。P2/P3 只从 P1 导入 helper，不调用其完整 evaluator。

同提交 `docs/a/source-manifest.json` 与原始 Git blob SHA256 核对：`contest_io.py=d5936908e4c261c7003b78e783f30bd7d65cb38d6b53a269ea67f0103cac848e`；P1=`2095f188a6c24ce3899f156bef21d50dcd87cbd9368488046b1e77e2bf91af3f`；P2=`0b39f84d5ec0a7fba9a4c92a598a9044b97ab79c71393824c1ba130ecfe6c464`；P3=`eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0`。加载器声明的完整 code manifest hash 为 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`；本轮未重新核对整个code树/原ZIP，也未调用加载器。

## 未覆盖与交接

交付前文档核对：JSON可解析，18条路由与6条中断情形均有同ID的Markdown行、无重复ID；P2/P3及pool/CLI由同机子Agent二次只读复核，未发现阻断性矛盾。此项是文档一致性检查，不是算法测试。

未覆盖：全部实验驱动的总调用数、冻结 helper 的逐语句运行语义与最坏耗时、C++ 内核全部语义/实际二进制、Windows进程/取消竞争实测、任意外部重试/共享调度、输出等价性/性能、网页。均不能由本矩阵标为通过。对这些范围或没有可靠阶段证据的实际费用，JSON使用 `null` 配合原因，不能当作数值0。

建议技术接收者先核对两个问题：共享调度是否把完整E1也纳入预算；面对自动回退和“已完成但响应丢失”时，是否保留最坏预留直到获得可归因证据。全池truth、shortlist确认与重试必须在调用方另外累计。若需要 native-only 或持久started协议，应另立实现范围及验证，不在本静态任务中改接口。

交付通过本分支PR和Issue #15给出完整提交SHA与可回读链接；不合并。Atlas在接手时验签到cursor95，本人完整board只有旧FAST review卡，grant也仅旧卡；因此没有把新审计擅自写成旧FAST doing或自行建卡。若队长后续建立独立卡/授权，再按字段版本签名提交；文档交付与技术复核/accepted分开记录。
