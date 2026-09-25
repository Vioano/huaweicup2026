# 部分预加载的离线分桶编译

这是一份**保存快照上的静态候选**，不是官方 P3 编译或成绩。`compile.py` 不导入官方模块，不调用 Task/Step1/Step2/Step3/E0/solver/VM；没有修改归核、其他作业顺序、其他核或冻结输入。三个输入文件的 SHA-256 记录在 `structure-table.json`。本目录为离线研究构造。

接口：`compile_split(plan, snapshots, certificate, core, head_count)` 返回 `(new_plan, predicted_words_by_core, facts)`。`new_plan` 仅含官方允许的 `node_to_subgraph` 和 `core_schedules`；它把指定下游核的首个 pilot 子图按原计算链前 `head_count` 个操作拆成 head/tail，新 tail 子图紧随 head。原 pilot、其余操作及其他核的归核不变。`predicted_words_by_core` 是按保存的 Step1 原始字稳定分桶后的**预测 pre-Step2 字**。

COPY_IN 归到最早计算读者桶，COPY_OUT 归到最晚计算写者桶。离线守卫核对了保存的原分桶字、pilot 逐操作链、两字段全覆盖、目标核计算投影不变、Task 全部原依赖拓扑、L1/UB 闭区间生命期峰值不高于原静态证书，以及五核 1,678 操作上的数据边、Pipe FIFO 边、跨核 COPY 边联合图无环。该联合图在示例中有 3,825 条去重边，**尚不含 Step3 内存复用边**。

在保存的 044/K5 快照上，core2 pilot 含17个计算操作、7笔原前缀冷读。本次仅覆盖 **cold-input breakpoint restricted family**：按首个冷读消费者变化去重，取 `(h,q)=(1,0),(2,1),(5,2),(7,3),(10,4),(12,5),(15,6)`；七个均通过上述静态守卫。中途激活 COPY 或 COPY_OUT 的归桶也可能随 `h` 改变，即使冷读数 `q` 不变，因此这七个断点**不覆盖全部合法 h 或全部可能的 MTE2 队列**。`structure-table.json` 只列此受限族，没有枚举同一 `q` 的任意 `h` 做性能扫描。示例事前固定取偏中间的 `(h,q)=(10,4)` 展示转换能力，未依据成绩选择；仅产一份 `example-plan.json` 和目标核的 `example-predicted-word.json`。其前四笔冷读后有两笔 pilot 激活 COPY，MTE2 位置为4、5，后三笔原前缀冷读位于其后；闭区间峰值为 L1 516,480 B、UB 0 B，等于保存的原证书峰值。**这不是单激活模型，且并未预测 Makespan 改善。**

运行：`python3 -B results/a/q3-nikolastarx/partial-bucket-compile-20260925/compile.py`，输出 `{"breakpoints":7,"passed":7,"example_h":10}`。一次候选编译的图和字处理为 `O(V+E+Σ_t producers(t)·consumers(t))` 时间及空间；七个断点分别编译。这里的 `V/E` 是已保存 Task 规模，非官方 Task 构建成本。

剩余验证：新方案仍须经过冻结官方方案检查、Task 重新构建、Step2/Step3、内存复用依赖和 E0；保存快照同归核时 Task/COPY 身份不变是当前转换的前提，未由本轮官方调用复核。共享 DDR、FIFO Cache、多个激活释放时刻和实际容量事件可能改变结果；当前仅交可证伪的构造接口与静态筛选。实际模型 token 用量不可见。

审计补充：六项守卫测试复现过非规范数字键被静默合并的问题；现已拒绝非规范键与非整数子图标签，负例改为断言拒绝。证书仍是调用者提供的可信输入，实际实验入口必须固定其文件SHA与快照身份；本工具未单独认证任意外来证书。
