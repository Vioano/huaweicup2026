# R5 两份证书只读审计（2026-09-25）

范围：只读最终答复、附件代码/静态 JSON 与冻结官方源码；未执行作者程序、官方 Task/Step2/Step3/E0，也未独立复现 097 数字。

源码锚点：本次读取的官方文件均位于 `data/raw/a/official/code/`；附件锚点位于 `AI chats/20260924-Pro-P3-归约森林切分/附件/`。审阅使用 Sol 子任务与主会话对关键源码复核，已暴露于作者论证，不声称盲审或机器证明。官方代码字节集合身份沿用 leaf-tile 机制 manifest 的 `de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。

## 1. 未来用途包络

**条件命题基本成立，不能直接将静态 JSON 当官方结论。** Step2 在每次操作分配后才检查容量，排除当前操作的 tensor，从其余活跃 tensor 按最远下一次使用换出（`schedule_step2.py:208-257`）。若 R5 `E_j` 确实覆盖同一核上所有下一次使用不晚于 `H_j` 的活跃 L1 对象，且这些对象总量≤C，溢出时必先有更晚使用的候选可换；归纳可保住原计算输出与本 tile 内已开始复用的输入。作者 `r05-leftdeep_tile.py:268-305` 对计算输出及 `[j,H_j]` 的不同外部输入计数；`r05-README.md:36-57` 列出必要结构守卫。根 COPY_OUT 须紧随根桶、输入 COPY_IN 须位于首个消费者桶；官方分桶是稳定按子图排序（`multicore_cut_evaluate_problem_3.py:51-67,166-187,253-259`）。若有内部 COPY、跨树中间量消费者或不同桶排序，上述结论不能外推。

有一个需要收紧的说法：`r05-README.md:48-49` 的“no second reload ... during its uses in one tile/chain-position block”只对**已开始使用且尚有本 block 用途**的 key 成立；从前一 tile 留下、在本 tile 首次使用前被换出可再装入，作者正文 `RESPONSE...visible.txt:329-339` 已允许此情况。`r05-leftdeep_tile.py:249-251` 给出的 6,815,744 B 装入和 2,555,904 B 额外 COPY 因而是有条件上界，非 DDR 物理下界或实测。`r05-case097_static_certificate.json` 自报零官方调用。

最小独立验证：只对已选 097/k1 计划做**一次**原版展开，核对重建后的逐核 `seq` 与作者 word/COPY 桶、Step2 `spill_records`：原计算输出 0 spill；每个 (tile,chain-position,key) 的 tile 内首次消费之后无再次 `COPY_IN`；输入 reload 字节≤2,555,904。失败时保存首个反例的活跃集合、next-use、`H_j`、`E_j`，不要继续评分。

## 2. prepared DAG 最长路

**在真正完整的 prepared graph 上，两次最长路是合理的条件性时间界。** `schedule_step3.py:595-609,675-702` 把内存复用边写入 execution_graph 并固定每条 pipe 的次序；P3 事件循环仅等图前驱、单槽 pipe、跨核释放，COPY 共享 DDR/Cache pool（`multicore_cut_evaluate_problem_3.py:323-325,352-390,436-465,523-581`）。每核 MTE2/MTE3 各一槽，DDR 同时至多 2k 条；Cache_READ 只由 MTE2 COPY_IN 使用，同时至多 k 条。公平分带宽使单个 COPY 的完成历时落在独占服务与相应并发倍数之内，整数向上取整仍被作者 `r05-m_debt_certificate.py:44-51` 的整倍数上界涵盖。固定 DAG 上，非 COPY 的固定 cycles、全部 tensor/内存边、pipe FIFO、跨核延迟齐备时，最短/最长权重传播分别界住实际 Makespan；`r05-m_debt_certificate.py:64-107` 的累计 M 空闲公式亦成立。

**实现的证书入口尚未证明输入完整性。** `r05-m_debt_certificate.py:17-35,54-61` 只检查 pipe 覆盖，不核验 `graph` 是否官方同一方案的 `execution_graph`、`MEMORY_REUSE` 是否完整、`cross_links` 是否完整、参数/哈希是否匹配。删去一条复用边就会使所谓 upper 低于真实完成时间：最小 DAG 为 A(旧 tensor 的最后读者)→B(复用其容量的新 COPY)，同 pipe 上另有长操作阻住 A；若漏 A→B，B 可在静态图中先完成，其后继 M 的 upper 被低估。该缺口是**证书输入契约/验证缺口**，不是两遍 DAG 定理的反例。作者 `r05-README.md:82-96` 也明确新候选尚无 prepared graph，故当前没有官方时延证书，10,559,344 不可作官方 Makespan 预测。

最小独立验证：从一次官方展开直接导出 `prepared['graph']` 与 `pipe_ops`、全部 `cross_links`，对照官方 `op_preds`、四 pipe 覆盖、`MEMORY_REUSE` 边数及 config；再计算上下界，并检查一次正式 E0 的每个 COPY 实际时长及总 Makespan 是否落入区间。若只给某个手工 JSON，最多称该 JSON 的抽象 DAG 界。

## 本轮接受范围

接受其作为有明确守卫的下一步证明路线，不接受附件静态数字为官方证书；下一次授权动作应先验证真实 Task/COPY 桶与 incarnation 依赖完整性，失败即保留反例，不进入形状扩参。已经完成的本机 4×4 逐层机制实验与作者 8×4 交错方案是不同计划，前者结果不能代替后者验证。本次没有新增 E0、Task 或 Step3 调用。
