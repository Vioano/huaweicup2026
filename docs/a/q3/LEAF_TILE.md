# Cartesian 左深归约链的叶片分 tile 静态原型

`src/q3/leaf_tile.py` 提供 `transform(index, plan, capacity)`，输入已经合法的 singleton 方案，输出仍只含 `node_to_subgraph`、`core_schedules`。它保持每个原始 compute op 的 subgraph ID 和核心归属，只改核内顺序。`construct(index, cores, capacity)` 是包装入口，先取 `forest_memory_order` 的实际整树分核方案，再调用 `transform`。该原型未接入在线候选选择；2026-09-25 已完成下述单格 P3 机制评价。

## 可识别结构

入口沿用 `forest_reuse_grid.recognize` 的完整 Cartesian 网格识别和 `forest_memory_order._original_tree` 的原边树检查，并逐张量验证：存在 `m×n` 个独立树格，每格有相同数量 `L≥2` 的独立 `PIPE_M` MATMUL 叶与 `L−1` 个原始 `PIPE_V` ADD，按原边形成严格左深链。首格的底层两个 M 叶固定一个标签顺序；其他格允许交换这两个叶，再按原始共享输入身份与已标记格对齐。之后的叶序由原 ADD 链唯一确定；所有格的同序叶必须分别读取该行、该列在同序号的同一个原始 L1 输入张量。每个组每个序号使用一个不同且由原始 COPY_IN 产生的输入；MATMUL 恰读这两个张量，ADD 恰读两个原始树孩子的输出。各格相应 M/ADD 的周期序列、两个轴的输入尺寸及 compute 输出尺寸一致，整棵树在同一核。任一关系不能从原图与输入计划核实，就抛 `UnsupportedStructure`。守卫不查询 case 编号、8×8、52 叶或固定字节数。

对给定 tile 高 `p`、宽 `q`，按两轴原始组的确定顺序切矩形。每核只取它已经拥有的格与矩形的交集；空交集忽略。对每个非空交集，按叶轮次 `t=0…L−1` 输出该交集所有 M；当 `t≥1` 时接着输出这批格对应的原始 ADD。完成该 tile 才进入下一 tile。这个 word 是原图的拓扑序：第一个 ADD 等待两个已列出的叶，以后的 ADD 等待本轮叶和上轮 ADD。不同树无 compute 依赖。输出计划再由 `derive_multicore_plan` 验证，且代码显式核对 op 覆盖、subgraph 映射和核心归属。

## 有限代数选择

设两轴每个叶输入大小为 `a,b`，每个 M/ADD 输出大小为 `s`，L1 容量为 `C`。完整 `p×q` tile 的理想单层集合上界是 `Q(p,q)=(2pq+1)s+pa+qb`：一格一个旧累加和一个本轮 M 输出，加一个 ADD 分配瞬态，以及本轮共享输入。实际所有权可能稀疏，故代码对每个核与矩形交集 `T` 计算

`Q_T=(2|T|+1)s+a·|rows(T)|+b·|cols(T)|`，`D_T=a·|rows(T)|+b·|cols(T)|`。

穷举有限的 `1≤p≤m,1≤q≤n`，丢弃 `max_T Q_T>C` 的形状；余者按 `Σ_T D_T` 最小、`max_T Q_T` 最小、`p` 最小、`q` 最小作确定性决胜。这个 `D` 是每个叶轮次中、按当前 tile 切分重复计算的输入 COPY 字节代理；同一 tensor 跨 tile 是否真的需重新 COPY，取决于 Step2 的寿命与 spill，它不是官方搬运量。全候选代数枚举对 `mn` 种形状各扫 `mn` 格，约 `O((mn)^2+|V|+|E|)` 时间、`O(|V|+|E|+mn)` 空间，不调用 E0。输入计划和官方 `derive_multicore_plan` 自身的检查成本另计。该规则不宣称得到 Makespan 最优 tile。

`Q_T≤C` **只证明当前 tile 当前叶层的理想张量集合能放入 L1**，不证明官方零 spill。别的 tile 未来仍需的共享输入可能在场；COPY_IN/根输出瞬态、Step2 Belady 换出、Step3 地址复用边和 P3 Cache 的发射/完成时序都不包含在 `Q_T` 内。即使 spill 字节下降，M 的总间隙也可能增加。因此该候选必须在固定源码、预算、原始结果和调用账下另作官方评价后，才能作为成绩或在线分支；目前只是一条静态可证伪路径。

## 当前静态检查

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.q3.test_leaf_tile -v`：6 个测试通过。小型 3×4、3 叶图在 `C=2200` 时选出 2×4，`D=3080 B/leaf round`、`Qmax=2091 B`；两核输入计划的原 op/core 归属保持，错配叶序共享输入与平衡归约树两个负例被拒绝，底层双叶 op ID 次序不一致仍可按张量身份对齐。对原始 `case_097.json` 仅执行一次本地构造与 `derive_multicore_plan` 合法性检查：选出 4×4，`D=163840 B/leaf round`、`Qmax=446464 B`，op 数与原树方案一致。这里没有运行 Task 构造、Step2、Step3、P3 E0 或 solver，也没有新增官方成绩。

## 一次可证伪评价的预登记

`src/q3/leaf_tile_probe.py prepare` 使用上述固定候选规则，只变换已有 forest 的 097/k1 方案；`gap_frequency_probe.evidence` 核对已有 forest/band 两个对照的固定提交、图/配置、方案和结果原件。准备阶段只生成一个方案和 manifest，零 Task/Step3/E0。随后 `run` 必须提供该 manifest 的 SHA-256、协调会话的新资源准入记录及实际资源预检文件；准入字符串只是来源记录，不自动授予共享主机权限。

本次预算只有 **1 次新 P3 E0，0 P2、0 solver、0 重试、1 worker，子进程最多 60 秒，进程组 RSS 采样警戒 512 MiB**。执行用独占的新 `evaluation/` 目录并在调用前落账；失败保留，不覆盖重跑。资源窗口不足时只保留准备材料。引用的既有 097 依赖探针预算已用完，本次不重建额外 Task/Step3；新 P3 自身内部的官方准备当然属于这一次 E0。

评价前已明确否证条件：候选即使减小搬运量，若累计 M 等待或官方 Makespan 上升，就不能直接接入求解器；若 M 改善但 spill/extra 上升，记录取舍，不能声称各指标全面改进。它是通用规则在已见机制样本上的单次实验，不是一个新算法的全量成绩，也不改变现有 forest500 榜单。

该预算已执行完：097/k1 Makespan 从 10,746,146 降到 10,662,163，extra/spill 从 11,665,408 B 降到 4,026,368 B，字节 hit 降到 0；没有新增 P2 配对。完整原件、时钟分解、资源与局限见[单次报告](../../../results/a/q3-nikolastarx/leaf-tile-097-one-shot-20260925/REPORT.md)。不能复用已耗尽预算再跑一格。
