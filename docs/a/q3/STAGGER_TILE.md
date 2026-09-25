# 左深链交错 tile 静态原型

入口 `src.q3.stagger_tile.transform(index, plan, capacity, bandwidth=60)` 返回原始计算操作的双字段计划与元数据。只改 singleton 子图的逐核顺序；原图、归约结合关系、子图映射和每棵树的 owner 均保持。实现不调用官方 Task、Step2、Step3 或 E0。

每个 owner 与矩形的交集形成一个 tile。按叶位置遍历 tile；每发当前 MATMUL，随后发前一个 pending 的**原始** ADD，tile 末排空 pending。形状只枚举 `1≤p≤m, 1≤q≤n`，不搜索 owner、切图或官方分数。

结构守卫来自 `leaf_tile._chains` 和原树校验：完整 Cartesian 双轴、同长同工作量的严格左深链、每个叶位置唯一原始共享输入、正大小 L1 tensor。额外核对精确 tensor 端口、唯一 COPY_IN DDR backing（原始 DDR 输入无 producer 且只由该 COPY_IN 读取）、根 COPY_OUT（DDR 输出只由该 COPY_OUT 产生且无人读取）、内部输出唯一原始读者、无额外 COPY；输入计划须为 singleton 且每棵原树在同一核。所有 MATMUL 必须具有同一正 cycles，所有 ADD 也必须具有同一正 cycles，且 MATMUL cycles ≥ ADD cycles；否则 service 模板不适用。不能通过守卫即拒绝，不降级为未经证明的计划。

每个 tile 计算未来用途包络：在计算位置 `j` 统计仍活跃的原始计算输出；取已开始用途对象的最晚本 tile 用途 `H(j)`；再统计 `[j,H(j)]` 内不同外部输入的总字节，包括未来首次使用的键。要求每点总量不超过 L1 容量。另要求 `(tile_cell_count+3)s + row_count·a + col_count·b + a+b ≤ C`，表达 pending ADD 与下一次 MATMUL 的保留空间。这两项是静态条件，并非真实地址分配或总溢出量。

可行形状以作者 r05 的条件 service 表达式 `W_core + 2k·(input_units + root_output_units) + tile_count·ADD_cycles` 排序，再按总条件输入字节、最大包络、`p,q` 破同分。`input_units` 按每次复制向上取整到 `bandwidth`，`W_core` 是原始 MATMUL cycles 总和。该值仅作形状排序代理；Step3 的物理 buffer 复用、credit 等待和 Cache 行为可能增加实际 Makespan，故它不是官方时延预测或保证。输入字节也是满足特定 Step2 singleton 重建与最远未来用途规则时的条件界，元数据不称实测。

设原始计算节点数 `N`、边数 `E`、形状数 `H=m·n`。当前实现每形状重建 tile 和滑动窗口包络，时间 `O(H·(N+E) log N)`，窗口及节点表空间 `O(N+E)`。已有静态测试以小图独立逐窗口直算核对包络，检查 owner、拓扑、错位叶拒绝及真实 097 的 8×4 结果；它们不构成官方方案质量或时延验收。

来源：`AI chats/20260924-Pro-P3-归约森林切分/附件/r05-leftdeep_tile.py`、同目录 `r05-README.md`；限制与未验证前提见 `results/a/q3-nikolastarx/pro-r05-independent-20260925/REVIEW.md`。
