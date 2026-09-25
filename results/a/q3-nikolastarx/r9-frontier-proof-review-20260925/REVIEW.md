# R9 singleton 桶前沿与全路径证明独立审查

结论：在当前冻结的官方 P3 Task/Step2/Step3 语义、R9 列明的 singleton 与原图结构守卫下，`F<=capacity => Step2 无 spill` 的反证法成立；每个原计算 op 有片上输出这一条件足以排除 `MEMORY_REUSE` 从较晚 singleton 桶反指较早分配桶。COPY 输入/输出与 DDR→UB 映射已被区间定义覆盖。把四条 pipe FIFO、内存边和 cross_links 投影到 `H_seq` 后，三层候选的跨核释放边数上界为 4。**这是条件定理及两份原图的静态检查，不是官方 prepared 图或成绩的验收。** 本审查没有运行官方 Task、Step1/2/3、P2/P3/E0，也没有调用 `pipe_bound`。

## 身份与实际检查

工作树 HEAD `c1edb49324fd8ff45cabecec02cf051ab5ddd119`；R9 报告所称输入提交 `c960cd38724fc8d5cc8c4e8942a58cdcf74fdc43` 只作为作者记录，本审查按下列实际字节核对，未把两个 HEAD 视为相同。所有路径相对本 worktree。文件 SHA-256：

| 文件 | SHA-256 |
| --- | --- |
| `AI chats/20260925-Pro-P3-多层查询亲和/附件/R9_R9_REPORT.md` | `09f0b284c66b8792c0cbdfee2d42266eb665a11fc66460751438895a5c7744d9` |
| 同目录 `R9_SOURCE_EXCERPTS.md` | `f4e54b4f468141a621663f56e9dadbfa290be46bbe2787945c7f3537859dc747` |
| 同目录 `R9_layered_affinity_r9.py` | `2e6221b4e618d2007aa451db7466d6d985e6347135154f38f6cb46d47501f131` |
| 同目录 `R9_candidate_005_metadata.json` / `R9_candidate_086_metadata.json` | `16b751fdfb5a62a9821fd552dc8aa63f62eb959eb39072bc1dd3dc6563c412e2` / `95daad19dcdf87fe58512dc105298ad010f7dfdb79f9af89cd8cba34cf60f5bb` |
| 同目录 `R9_candidate_005_plan.json` / `R9_candidate_086_plan.json` | `2885b28a512598e4bae525c7bf4b214ac9b2452de19425603fcdea2ae8e7038a` / `f2111af54fcc3c11048663db149a93290dbe4558e7d5b7eecf8ec49e847022e6` |
| 同目录 `R9_candidate_005_evidence.json` / `R9_candidate_086_evidence.json` | `f570f6b6ca8d91fc1eec0ffed5917202014d1f4873385831e9398d952f4e5ac6` / `531412aefcf839c1e752bfa37bc7d0ce765f5e774c52109c9c13500e130c45d1` |
| `data/raw/a/official/data/case_005.json` / `case_086.json` | `c2b378c882a3039e3d66bac6cbcba39317107339b6f38d5bce1b09379839799f` / `ef91fda2692fd0add63db3c7f677e4e03c8d115d97db3cb959cffc62fff2434a` |
| `data/raw/a/official/data/config.txt` | `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9` |
| `data/raw/a/official/code/multicore_cut_evaluate_problem_3.py` | `eab1504dead881f4b67c0f0498cbc2dbbd9039dc3c9d198c6af58773c127eeb0` |
| `data/raw/a/official/code/schedule_step2.py` / `schedule_step3.py` | `2836baac176f4e0bdd9eec59b8d9ce254e209e5f7a251e23837ab684312fa0c3` / `50053db0436f1d166dd75436693ba3af49b5c339576beb6e7299477f6b69fc7a` |
| `data/raw/a/official/code/schedule_step1.py` / `stub_multicore_cut_and_schedule.py` | `d8fe721ff3dbe036e34a20c00cce6430960860000a49eb467e63465f76b84034` / `0a3a3b79b5173b466fc05fc8d33b72d11d90b4df78995435853d91c632a35892` |

我只用 Python 标准库读取 JSON 做独立静态复算，没有 import R9 或官方调度模块。005/086 分别有 4113/5274 个非 COPY op；plan 仅有规定的两个顶层字段，mapping、R9 ownership、全局 priority 与各核 word 均恰好覆盖这些 op 一次；逐个非 COPY op 均有原图片上输出。用原图每个 tensor 的唯一 producer、本核所有 eligible consumers、plan 核内位置重建闭区间并按 L1/UB 求前缀和，五核峰值分别重现 R9 metadata：005 为 L1 `[15168,14976,14976,40288,40288]`、UB `[21844,21844,21844,23668,23668]`；086 为 L1 `[16320,16128,33408,43456,44416]`、UB `[27604,27604,52852,38164,38164]`。容量取固定配置 L1=524288、UB=131072。独立用原 compute DAG 加每核相邻 word 边，按 R9 给的全局 priority 检查全部边前向，最长跨核边数两例均为 4。原图远端 compute 依赖没有发现不属于 S→私有或同层 P→A 的边。这证实计划与原图上的静态性质；没有独立重建 R9 的 row 识别/DSU 证明。

## Step2：闭区间是充分证书

官方 P3 builder 每核一 Task，并只映射 eligible 非 COPY op；`DDR` 原 tensor 的本地副本转成 `UB`（`multicore_cut_evaluate_problem_3.py:69-95,141-164`）。无 eligible producer 的输入在首个消费子图建 COPY_IN；原图输出及跨核传输在生产者子图建 COPY_OUT，远端核在首个消费者子图建 COPY_IN（同文件 `:166-215`）。singleton 下每个子图恰有一个原计算 op。`_prioritize_task_seq` 稳定按子图序归桶，保留 Step1 的桶内拓扑顺序并再次检查拓扑（同文件 `:51-67,244-259`）。因此该桶的所有新输入 COPY_IN 位于计算前，所有该桶输出 COPY_OUT 位于计算后；它们触及的是这个计算的原 tensor 输入/输出。`R9_layered_affinity_r9.py:368-402` 对每个 `(core,tensor)` 从本核 producer 与所有消费者位置取闭区间，并将 DDR 原位置按 builder 转成 UB；一个 tensor 在本核只计一次，跨核目标核的副本另计。旁路 tensor 延续到最后真实消费者，未按层界提前释放。

`schedule_step2.py:39-67,113-136` 把每个非 DDR tensor 的 producer/consumer 都作为 use；在无既往 spill 的归纳假设下，活跃集合恰是这些 first..last 闭区间。每个 bucket 的峰值可在其计算 op 的 alloc 后、execute/free 前达到；末次输入不会先释放（同文件 `:204-289`）。故首次超容量前若每池每桶 `F<=C`，该步占用不可能超容量，`pending_spills` 仍为空；incarnation 生成只随 pending spill 发生（同文件 `:291-405`）。这证明**Step2 无 spill**，不等于 Step3 真实并发驻留峰值等于 F。一个容量反例说明闭端点不能省：容量 1、旧输入在同桶最后消费且新输出在同桶首次生产，各 1 byte；用半开或“先 free 再 alloc”会错误地判为 1，官方 Step2 在该步检查 2。

## Step3：内存边与四 pipe 的投影

无 spill 后每个片上 tensor 只有原 Task 的一个物理版本；Step3 在 producer 发射时 alloc，在全部消费者（含 COPY_OUT）结束后 free（`schedule_step3.py:114-139,239-279`）。释放额度记录旧 tensor 所有消费者，死输出取 producer；复用额度可拆并生成 `source→new producer` 的 MEMORY_REUSE 边（同文件 `:144-209,583-609`）。`allocation_order` 按 `seq_ext` 取所有有片上输出的 op，并在发射时严格推进（同文件 `:281-300,458-493`）。本次原图每个非 COPY op 都有片上输出；每个本地 COPY_IN 也产生片上输出。**输出大小可以为 0：当前冻结源码的 `managed_tensors` 与 `allocation_order` 只检查 pool/输出存在，不按 size 过滤（同文件 `:126-129,289-292`）；零字节输出仍保留 allocation rank 与发射门槛。** 因而旧 tensor 的计算消费者若属于更晚桶，其 allocation rank 也晚于新 producer，不可能先完成并提供复用额度。旧 tensor 的 COPY_OUT 虽无片上输出，却只在其原 producer 桶；该 producer 若能先产出旧 tensor，桶不晚于新 allocation 桶。同桶反向也不可能：COPY_IN 在唯一计算前、COPY_OUT 在它之后；旧 tensor 不能在本桶新输入分配前由该计算/输出 COPY 完成释放。因此所有实际 MEMORY_REUSE 边在不同 singleton 桶上严格前向。这个论证对**产生的边**成立，不保证没有内存边、不保证无等待、也不代替官方 prepared 图逐边回读。

必要条件不能删除。最小失败形态是三桶：桶 0 产出旧 tensor；桶 1 的 M-pipe producer 等待较慢的独立前驱；桶 2 的 V-pipe **无片上输出** sink 消费旧 tensor，且可先执行释放它。sink 不在 `allocation_order`，后发射的桶 1 producer 可复用该额度，得到桶 2→桶 1 的反向 MEMORY_REUSE 边。该结构是对“任何 compute 都能套用前向引理”的抽象反例，不是两份官方图上的实测反例，也不声称同时满足本轮 F 容量条件。

原 M/V、重建的 MTE2/MTE3 四条 pipe 的 FIFO 都取 `seq_ext` 投影（`schedule_step3.py:281-288`；prepared 返回 `:675-703`）。桶稳定排序使 FIFO 边在桶投影上不下降；桶内 COPY 只投影到同一个计算节点。远端 cross_link 明确由 COPY_OUT→COPY_IN 连接（`multicore_cut_evaluate_problem_3.py:189-215,346-350`），投影到原 producer→目标核首个 consumer，严格沿全局 priority 前进。注意这一步压缩了 COPY 服务节点，仅用于依赖路径的方向及跨核边数，不能拿压缩后的周期作官方 makespan 界。

## 三层 crossing≤4 的适用边界

`H_seq` 为原 compute DAG 加每核整个 word 的相邻边。每核新增边同核且阶段不倒退。R9 的 `decompose` 检查 S 祖先闭合、跨轨道私有边只能是已识别同层 P→A K/V、所有原边阶段不倒退（`R9_layered_affinity_r9.py:182-257`）；优先序逐阶段且全局拓扑（`:338-366`）。S 的各弱连通分量各在单核，路径离开 S 后不能回去，至多一次 S→私有跨核。每层只有 P_l→A_l 可跨轨道，阶段序禁止 A_l 回到 P_l，故每层至多一次。三层 `1+3=4`。`H_seq` 的边对 COPY FIFO、内存边及 cross_links 的上述投影给出路径包络，故 full prepared 联合图若符合冻结构造，不会多出第 5 次跨核释放。独立对两计划的 H_seq 重算均得 4。

不能把 4 解释为 COPY 总数、DDR 等待总量或 makespan 增量上界。也不能说 `H_seq` 的 `L_delta` 是官方周期上下界。若去掉“跨轨道私有边只允许同层 P→A”守卫，一个 A_l→另一私有轨道的直接边就可能在一层形成第二次跨核；若去掉阶段单调，一个路径可再次进入 P_l。这些是最小结构反例类别，当前两图该守卫静态检查均未失败。

## 下一阶段 prepared 原件必须逐项证伪

1. 固定图/config/plan/source 哈希；保留原始 Task、Step2 `spill_records`/`overflow_log`、prepared `execution_graph`、每条 pipe 的 `pipe_ops`、`memory_dependencies`、`memory_peak` 与全部 `cross_links` 原件。核对非 COPY op 恰好 4113/5274 个且各一次，每核 singleton word 与 plan 对齐，Step2 无 spill、无新 incarnation；若不符即停止，不能用静态 metadata 代替。
2. 逐 `(core,tid)` 核对 Task 本地 pool/size、COPY_IN 最早消费者桶、COPY_OUT 唯一生产者桶、DDR→UB、本核所有消费者及闭区间；确认 Task COPY bytes 和远端 COPY 对数（作者预测 005：1,595,646 bytes/381 对；086：1,710,750 bytes/429 对）。对不同或缺失的 tensor 保留原图、Task 端点，不直接归咎于评分。
3. 对每条 prepared MEMORY_REUSE 记录 source/target op、旧 tensor、WAR/WAW、桶编号；要求跨桶严格前向，同桶若出现必须解释完整 Step3 操作顺序并重审引理。核对 **Step3 核内准备模拟** 的 `memory_peak≤capacity`；这不是 P3 最终多核事件时序下的真实峰值，若要声称后者还需单独的最终 result/trace。F 不能替代前一项。
4. 由 prepared 原始+内存依赖、四条**实际** pipe FIFO 和全部 cross_links 建联合 DAG，检查无环并重新求路径跨核释放边数≤4。不能只用 compute DAG 或 R9 metadata 的 H_seq 值。任何失败先保存原件、审查证明/实现，停止本轮候选，不追加搜索。

未证明事项：官方 prepared 结果、实际 Step3 运行时峰值/内存边具体集合、P3/P2/E0 成绩、M3 改善、G 改善、全 100 图适用、完整冷 solver 效率。报告的静态耗时也不是比赛口径的端到端求解耗时。官方首要指标是 Makespan；5–10 分钟是避免暴力迭代的用例级生成建议，不是该模拟周期，也不是 P3 的硬淘汰线。本审查不支持放宽固定候选/评价预算。
