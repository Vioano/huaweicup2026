# E1/E2 独立评估：当前实现不足，尚无极限证据

> 本文件记录第一阶段的只读审查。用户随后明确授权隔离机制原型与实跑探索；后续路线、代码及结果见同目录 `ACCELERATION_HANDOFF.md` 和 `probe/`。第一阶段的“没有改写评估器”不代表后续未制作研究原型；正式 `src/`、`tests/` 和官方原件始终未改。

2026-09-23；评估 session `nikolastarx/s-55b66a31d7bd49019122a179563dc1d2`。固定 FAST PR20 HEAD 为 `d83d5f32a1c23f6450aa9c15fa85891c4ebddd7f`，最新实现提交为 `8edccee2c85b3b46c55b0f08f3273b01d501f8b2`。本阶段仅审查、运行现有入口及诊断测量，没有改写评估器、测试或冻结材料，没有安装 Rust 或使用 Colab。

**结论：未达最终门槛。现有证据支持“E1 优化覆盖不足、E2 近似语义过粗”，不支持“已经达到理论极限”，也不支持笼统归咎于程序错误。Rust 值得作为后续热点实现候选，但不能修复现有 E2 模型的误差。**

## 1. 语言与真实执行路径

- E1 主实现是 Python。`src/eval_exact/problem1.py` 替换 Task 边界构图，并在私有 Step3 runtime 用带 schema/别名保护的复制替换通用 deepcopy；Step1、Step2、Step3 调度逻辑及全局事件模拟仍使用冻结官方 Python。
- E2 的 rank/event 两条实际图评估路线也是 Python，均只支持 Problem 1。rank 仅排序，event 是 Makespan 估计；均未实现完整官方结果/Trace 接口。
- C++17 与 Rust 文件是合成 TSV 特征的固定点排序小内核，不读取完整官方 graph/plan，也未接入实际 E1/E2 主路径。C++ 有字节一致的运行证据；Rust 未编译运行。本机 PATH 也未发现 rustc/cargo，未安装。
- 因此，这次不是“已优化到极限的 C++ 评估器与 Rust 的比较”。原生小内核的加速不能外推为完整评估器收益。

## 2. 本轮实际复跑

独立 worktree：`.worktrees/e1e2-assessment-20260923`，detached 于上述固定 HEAD。`a_materials.py --extract` 校验 114 个来源文件、100 个 case；`uv sync --locked` 使用 CPython 3.12.13。环境 macOS 27.0 arm64，18 个逻辑 CPU；各性能实验依次执行，不并行运行本会话的测量。

| 项目 | 本轮观察 | 能支持的结论 |
| --- | --- | --- |
| 现有测试 | E1 11、E2 16、native reference 5，全部通过 | 32 项有限回归通过；native 测试不是 Rust 编译验证 |
| 64 候选 | 现算 E0、保存 E0 JSON、当前 E1 完整输出逐项一致 | 同一 P1 开发池内未发现差分 |
| 3 个原基准例 | 完整输出一致；配对几何加速 1.2173 / 1.2081 / 1.2420× | 3 例合并几何均值 1.2223×，不足 3× |
| 补充大图 case_003 | 13,670 ops；完整输出一致；1.2519× | 大图亦未达 3×，排除仅靠三例规模小来解释全部不足 |
| E2 event 数值 | 误差 median 25.7591%、P95 28.8954%、max 30.6974%；64/64 均高估且超过 3% | 明确未达 1% / 3% |
| E2 shortlist | 两路线在该池 regret 均 0；Spearman rank 0.8568、event 0.8127 | 仅一个开发池，不能证明多池/封存保留率 |
| 同机同池速度 | E1 full / E2 rank 71.50×；E1 full / E2 event 66.96× | 当前内部指标路径有速度余量，联合验收仍失败 |

原三例为 case_001/019/080，4 核、seed 2026、子图大小 4–12、预热 1 次及配对 5 次；大图为 case_003，同 seed/核数、子图大小 50–100、预热 1 次及配对 3 次。四例 Makespan 分别 189027 / 141133 / 294124 / 758098。新增大图不是事先冻结的发布矩阵，不能把它与小矩阵事后合并包装成发布成绩。

64 池计时采用 64 个不同计划、常驻图、预热一次、三次交替引擎顺序；E1 full 总时长 4.1810 / 4.1946 / 4.1915 秒，event 0.06248 / 0.06205 / 0.06316 秒。E2 图准备另为 0.01426 秒。均不含 CLI 启动、文件序列化、最终 E1/E0 回退及整条搜索流程成本；E1 full 与 E2 内部指标的输出能力不同。该单池 E1 也尚未满足 3× 门槛，因此不能据此宣称最终 E2 联合标准通过。

`e2-routes.json` 中原脚本自动生成的 `recorded_e0_seconds_over_route_median` 使用历史 Windows E0 除本机 Mac 时间，约 506/468，**一律排除**。本报告的 71.50/66.96 来自重新同机计时的 `pool-readback.json`。

本轮没有重跑历史 169 微型或 FORM 的 372 次对照；不能把旧 FAST 3357d7e 的复核自动计入本轮 d83d5f3。最新 schema-copy 的更广对抗复核仍待团队交接。

## 3. E1：哪里还有空间，哪里已不值得继续抠

对新版本做了仅测量的函数包装，每例预热一次、测五次，结束后恢复原函数；没有优化算法或改变返回值。原始样本在 `profile-readback.json`，cProfile 原始文件另存。阶段占比取各次比例的中位数，嵌套的 inclusive 时间不可重复相加。

| 当前 E1 占比 | case_001 | case_019 | case_080 |
| --- | ---: | ---: | ---: |
| 边界索引 | 0.79% | 0.68% | 0.56% |
| schema-copy | 3.95% | 3.75% | 3.53% |
| Step3 准备，含局部模拟与上述复制 | 35.95% | 35.25% | 32.54% |
| Task 构建完成后的全局模拟与结果组装 | 41.32% | 40.73% | 48.36% |

边界索引已不是主瓶颈。即使把这不到 1% 的部分完全消除，也无法明显改变端到端速度。当前瓶颈同时分布在 Step3 和全局事件/组装层。

源码与 cProfile 还能定位具体候选：官方 P1 `retire()` 在每轮事件遍历全部 Task，并为活跃 Task 重新生成全部 op 键、检查全部完成状态（官方文件 369–373 行）；最后组装每个子图时反复筛选该核全部 op_entries（474–476 行）。case_080 中 retire 调用 4,261 次；Step3 `_build_graph_views` 累计调用 549 次。这些是可研究的重复扫描/对象构造成本，不是由评分语义直接推出的时间下界。是否能安全替换必须用 full JSON、异常及同刻事件回归验证，当前没有实施。

条件性的 Amdahl 推算：若只改善一个阶段，其他成本不变，则总收益受 `1/(1-f)` 限制。按本轮样本占比，即使 Step3 完全免费，相对 E0 也仅约 1.84–1.90×；即使整个后半段完全免费，也约 2.04–2.41×。这说明“只重写一个局部热点”在这些样本上不足以达 3×，**不是评估器整体的理论上限**。

从约 1.22× 提升至 3×，还需削减当前 E1 约 59% 的时间。若同时加速 Step3 与后半段（目前合计约 76–81%），在其余部分及调用成本完全不变的理想假设下，两段需要约 3.6–4.7× 局部提速。这给出了有价值的实验目标，但没有证明 Rust 或任何重写必然实现它。插桩有开销、样本有限，比例与推算均用于方向判断。

## 4. E2：是模型缺口，不能靠换语言或统一缩放解决

`src/eval_proxy/event_model.py:150` 明确将输入 COPY、计算、输出 COPY 三段直接相加。实际官方过程包含 COPY/计算重叠、固定 Pipe 顺序、内存复用依赖、共享 DDR 动态争用；该代理还省略 spill。当前 64 池实际 spill 新增字节全为 0，尚不能说明 spill 场景表现。

本轮额外做了两个诊断，均未改候选程序：

1. **用 E0 已保存的准确局部 Step3 时长替换代理 Task 时长，再进入同一粗粒度全局传播。**误差仍 median 5.7615%、P95 9.2211%。这独立复现成员的误差分解，说明只修局部时长不足，粗粒度全局组合也有误差。该实验依赖 E0 真值，只是诊断，不能作为可部署 E2 或速度证据。
2. **允许使用这同一开发池的全部标签，挑选使 P95 最小的统一正比例系数。**最优系数约 0.802746，P95 最低仍 4.1914%（此时 median 1.7367%），连同池最乐观缩放也过不了 3%。计算方法：对 64 个 E2/E0 比值排序，nearest-rank P95 要覆盖 61 个点；枚举连续 61 点区间，用 `scale=2/(r_min+r_max)` 最小化区间端点相对误差。全部比值可从 `pool-readback.json` 重算。

这个下界只适用于“给当前输出统一乘一个常数”的方法族。它不排除分层建模、表达重叠与争用的新模型，更不证明低误差高速评估在该问题上不可达。复杂校准需图级开发/校准/封存分离，不能用同图标签拟合后作为验收。

## 5. Rust 的判断与下一步优先级

**值得做一个针对真实热点的小范围 Rust 实验，但现在没有完整 Rust 性能证据，也没有开始实现。**

- E1：优先验证 Step3 与全局事件路径的数据结构、完成计数和重复构图成本。Rust 小原型应覆盖真实耗时内核，并计入 Python 交界的数据转换、加载、结果组装；仅再次移植合成评分公式不能回答本任务。一次批量传递官方输入/紧凑中间结构比逐 op 跨语言调用更值得比较，但仍待实际测量。
- E2：先验证能表达 COPY/Pipe 重叠与 DDR 共享的模型，分别量化局部和全局误差。在当前 Python 路线上先获得误差下降证据，再判断是否有必要用 Rust 换取更丰富模型的时间预算；单纯忠实移植现有近似，误差来源仍保留。
- 最小验证集须包括同刻发射/退休、DDR 重新结算、零周期/字节、空核、spill、FIFO 阻塞与异常出口；E1 保留整数、列表顺序、binary64 运算/ceil 行为。Q2/Q3 仍未支持，不能由 P1 外推。
- 3× 的可达性：有明确未处理热点，值得验证，尚未被证明可达或不可达。10× 与 1%/3% 联合可达性：当前有内部速度余量，但低误差与跨图泛化尚无证据；当前模型已明确失败。E1 后续变快还会提高 E2 相对速度要求，需重新联合测量。
- 后续以多图/多池、代表性 spill 与高争用范围、同机配对和完整流程成本收敛。当前 CI 的 smoke 工作流主要执行 demo/mailbox，不运行本轮 evaluator 矩阵，CI 绿不构成这些门槛通过。

## 6. 证据与交接

本目录 `e1-matrix/`、`e1-large/` 为原 benchmark 命令直接生成的 plan、逐对时间和 run.json；`e2-routes.json` 为原 compare_routes 输出；`pool-readback.json` 是独立现算 full 对照和同机吞吐；`profile-readback.json` / `case_001.pstats` / `case_080.pstats` 保存热点证据；`diagnostic-readback.json` 保存上述两项诊断及阶段比例。没有新增或修改 `src/`、`tests/`，没有写其他人的 worktree。

原命令复现（输出目录必须另选一个不存在的位置）：

```sh
python3 scripts/a_materials.py --extract
uv sync --locked
PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests/eval_exact -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests/eval_proxy -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests/eval_proxy_native -p 'test_*.py' -v
PYTHONDONTWRITEBYTECODE=1 uv run python -m src.eval_exact.benchmark --cases case_001.json case_019.json case_080.json --output-dir output/new-assessment/e1-matrix --seed 2026 --cores 4 --warmup 1 --repeats 5 --min-subgraph-size 4 --max-subgraph-size 12
PYTHONDONTWRITEBYTECODE=1 uv run python -m src.eval_exact.benchmark --cases case_003.json --output-dir output/new-assessment/e1-large --seed 2026 --cores 4 --warmup 1 --repeats 3 --min-subgraph-size 50 --max-subgraph-size 100
PYTHONDONTWRITEBYTECODE=1 uv run python -m src.eval_proxy.compare_routes --graph data/raw/a/official/data/case_001.json --config data/raw/a/official/data/config.txt --pool-dir results/a/proxy/r20260923-e2-dev64-gzip --output output/new-assessment/e2-routes.json --warmup 1 --repeats 3
```

完整查收快照包含 3 个 Issue、137 条评论，索引与正文已分批读取；本会话未发送团队 Issue 回复。实现继续等待调度，团队通知、Atlas 与合并由调度会话处理。
