# 固定 R9 融合器五核均值上限：独立只读审查

**限定结论。** 若融合规则固定为：只在冻结 R9 识别/分解成功且 `5<=tracks<=10` 的图尝试此构造，其他图及任何构造/验收失败图沿用同一份 Forest500 五核结果；005、086 若替换，只能用本次字节完全相同的两个 singleton plan；其余 11 个可能改变的图即使达到已有的通用合法下界，则五核 100 图平均加速比仍至多 **4.994650520967255 < 5**，缺口 **0.005349479032745**。这是该**限定融合规则及固定快照**的不可达证明，不是 R9 算法家族、其他计划、其他融合策略或官方 P3 最优值的上界。源码 `construct_layered` 本身没有 Forest fallback；87 图保持不变是待冻结融合器必须实现的外部前提，不能从当前构造函数自动推出。

## 输入身份与适用域

- 只读文件 SHA-256：`coverage.jsonl` `7c16f4bfb5eead50b68e1af18e1e40b30d01d72f627dd79eb0f7a8462db4ccfc`；`coverage_headroom.json` `342f114a4fac9428495ece5d8c1989d0b22ba7380041eb17930331b29fe5e852`；`arithmetic.json` `a529b4af29dc1e105e0a7f9cdbdfdfddce02918e1f2d26e8fe49ab4244c46d41`；`src/q3/layered_query_flow.py` `db197556787c7818cad21c47dca52e497ba84ba56e1717d4616977fda0556d33`；`global-bounds-20260925/bounds.csv` `bb8a21066f228f428ca2cab3d742c2eb6247cfbf1b281b30c588029a6ba9cd86`；`forest-current-headroom-20260925/cells-snapshot.json` `cf6021229b57458db772920faf8cdf995c0dc35a381d8f043254aa6a99f341cb`。
- 覆盖原件恰有 100 行：78 行在结构识别/分解被拒，22 行 `recognized_and_decomposed`。其中 9 行轨道数不在五核 DP 守卫 `[5,10]`，留下 13 行：005、009、040、047、049、053、069、071、072、075、082、085、086。`partition_tracks` 的硬守卫为 `1<=cores<=r<=10`（`layered_query_flow.py:255-256`），`construct_layered` 先识别、分解，再执行该 DP，随后还有容量、路径等守卫（`:451-495`）。13 只是**必要条件覆盖**，不保证构造完成、官方合法或成绩改进。该静态覆盖运行没有调用构造、Task、Step 或 E0。
- Forest 快照 cursor `12071`，500 个 `(case,cores)` 唯一格均来自 `q3-forest-memory-witness`、同一 run `q3-forest-full500-20260925-s59`。本审查从其 100 个五核格与 `bounds.csv` 的固定单核基线重算旧均值；`coverage_headroom.json` 的 13 个 `B/T/L_global_relaxation` 分别与上述快照/界表整数逐格一致，0 个不匹配。这是一份固定历史快照，不代表当前成绩台最新状态。
- 005/086 已归档固定计划字节 SHA-256 分别为 `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a`、`f2111af54fcc3c11048663db149a93290dbe4558e7d5b7eecf8ec49e847022e6`；本地 `layered-port-static-20260925/case_*/constructed/plan.json` 两份实算 SHA 与 R9 附件相同。若程序/参数/计划字节改变，须重核 fixed-plan 下界，不得复用此替换项。

## 下界为何可用于分母

其余 11 图使用 `global-bounds-20260925/REPORT.md` 的通用下界 `L=max(CP,ceil(W_M/5),ceil(W_V/5),Dmax)`：每个原计算 op 不可省，原依赖仍需满足，每核 M/V pipe 同类不能重叠。该界不依赖 R9 plan，可乐观地用于任何合法五核替换。

005、086 使用更强的**各自固定 plan** 下界 `L_fixed=21636/27109`，见归档 metadata 的 `compute_mv_fifo.Ldelta`。`layered_query_flow.py:400-424` 的图只有原 compute 依赖与计划各核 M/V FIFO，相邻原跨核依赖加固定 500-cycle release；它没有加入 COPY 服务、DDR/Cache 竞争或内存边。该计划若通过官方 Task/Step 并被 E0 合法执行，原 compute 仍各一次，同核原 M/V 顺序为提交的 singleton word 投影；跨核原 tensor 依赖由 COPY_OUT→500 等待→COPY_IN→消费者实现。因此删去这些非负耗时/额外限制只会缩短路径，`Makespan>=L_fixed`。这不是 `H_seq` 的串行化长度；后者不能充作周期下界。当前尚无这两计划的官方 prepared/结果，故此论证仍以固定源码/计划守卫及合法执行为条件；若计划不合法，限定融合器必须回退 Forest，该格不会获得更大增量。

## Fraction 算术（只读整数）

设 Forest 快照中图 `i` 的固定单核基线为 `B_i`，现有五核周期为 `T_i`。平均值用逐图比值的算术平均。令 `E` 为上述 13 图，`L_i` 对 005/086 取 `21636/27109`，对另 11 图取通用 `L_global`。每个候选即使被选中也有 `M_i>=L_i`；未替换则保持 `T_i`。本数据所有 13 个 `L_i<T_i`，故允许择优 fallback 的乐观上限仍为

`C = (Σ_{100} B_i/T_i)/100 + (Σ_{i∈E}(B_i/L_i - B_i/T_i))/100`。

用 Python `fractions.Fraction` 从快照及界表整数计算，`Forest=4.7576166788448955`；若 13 图全用通用松弛界，增量 `0.29876282927889936`、上限 `5.056379508123795`，**不能**据此排除 5。把 005/086 分别收紧至同字节计划界后，两图的最大增量仅 `0.012989053844691616`、`0.007425643714549355`；13 图增量合计 `0.2370338421223596`，上限 `4.994650520967255`，与 5 的严格差值 `0.005349479032744809`。这是有理数运算后仅在展示时转十进制；数值与 `coverage_headroom.json` 的来源整数一致。

## 不能外推的地方

这不说明 13 图可达到各下界，也不说明新的 R9 计划会改善 Makespan。即便全部在此融合器下合法且采用最乐观周期，仍跨不过 5；这只否定此**固定组合**作为达成五核目标的充分路线。换一个 005/086 分组/顺序、允许其他结构图被新方法修改、改变 87 图 fallback、换基线/快照，或目标改为 4.76/其他核数时，必须重新计算。也不能把不同候选逐格离线挑最优后的组合称为一份已冻结完整求解器成绩。未运行构造、Task、Step、E0、`pipe_bound`，未产生新官方分数。
