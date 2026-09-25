# 首批合桶的固定 Task 下界：仍值得最小官方验证

旧 044/5 核容量方案的完整 Task 下界为 **37,290 cycles**，已测官方 Makespan **38,390**；新首批合桶候选的下界为 **29,780**。新候选未评分。下界下降表示旧固定 COPY 队列的限制不再同样适用，不是已取得性能改进，也不是保证可以达到该下界。

1. **目标**：在不新增官方调用的条件下，判断已冻结 R6 候选是否已被合法下界排除，并校正原 26,842 compute-only 下界过松的问题。
2. **输入**：原始 044、官方固定配置，以及 `pipeline-prefix-static-20260925` 完整 Task/COPY 原件。静态 summary SHA `6f8d0680ca8ebcdf8b35269961881d6d13e7c0524cdea235bd341f4608906b10`；不重新构造 Task。旧完整官方结果 SHA `506a8d65c65b7bcd2957e2b20f31ba117fb3a244b9c366ff2342c421df626cd5`。
3. **输出**：`anchor.json`、`candidate.json` 给出下界、全部 COPY 下界时长、关键路径及容量检查；`summary.json` 保存源码/输入身份，`anchor-trace-audit.json` 为旧原件回查。
4. **限制**：只对这两个已经保存的固定计划各分析一次，未生成新候选。所有 Task 必须完整，生产者唯一、普通整数张量 ID、tensor 中转边、M/V 运算、单入单出 DDR COPY、原字序完整且闭区间容量合格。不覆盖 logical alias、多端口 COPY 或发生 spill 的计划。所有 Task/Step1/Step2/Step3/E0/solver 调用为 0。
5. **验收**：5 项合成数学守卫测试通过；旧官方原件中 314 个 COPY 的时长下界、COPY_IN key 和160个冷键声明成立，关键路径386节点的最早开始界不超过实测值。不是新的官方复跑或跨平台验收。
6. **下一步**：保留原已冻结的一次 prepare + 一次 P3 最小验证，预算不增加。实际窗口仍由总调度安排；新下界不证明官方准备一定成功，也不改变完整算法成绩。

## 为什么是下界

对每个核，将完整、无 spill 的 pre-Step2 顺序按 Pipe 投影；在全体操作上建立有向图：

- 张量生产者→消费者，包括 DDR 张量依赖；本实现遇到直接 op→op 边则拒绝，不漏边后继续声称适用。
- 同核同 Pipe 相邻操作→后续操作。
- 实际跨核 COPY_OUT→COPY_IN，并加配置的跨核等待500 cycles。

计算操作取 `max(1,cycles)`。COPY_OUT 取 `max(1,ceil(bytes/60))`。其他 COPY_IN 乐观按更快的 Cache/DDR 带宽取最短时长；若其**真实本地输出 Cache key 在全部 Task 的 COPY_IN 中恰好只出现一次**，则首次读取必定 miss，使用 DDR 60 B/cycle。缓存起初为空，仅 COPY_IN 完成时填入，COPY_OUT 不填入。拒绝多端口 COPY 避免把官方“全部输出/输入大小之和”误写为第一个张量大小；拒绝原张量别名字段避免 raw ID 与 `logical_tid` 混淆。整数规模守卫还限制了浮点除法边界。

逐操作的约束为 `start(v) >= start(u)+duration_lb(u)+delay(u,v)`。取该 DAG 的最长路结束时间。官方共享带宽竞争不能把操作缩短到独占时长以下；新增内存复用依赖也不会放松已保留的边。因此任一成功官方执行均不早于这条最长路。这里没有把虚拟分配顺序直接当作 P3 完成依赖，也没有混用不同计划的旧 singleton 下界。

无 spill 前提由完整 Task 的逐张量 first/last-use **闭区间**检查提供：同一步先分配输出，再释放用完的输入，峰值不超容量且没有初始片上驻留时，Step2 无需驱逐。若此条件失败，本实现拒绝签发该界。实际 Step3 可能增加同步边甚至出现执行问题；这个下界不代替其合法性验收。

冻结源码依据：

- `schedule_step2.py:443`：无 spill 时保留字序；`schedule_step3.py:281`：由字序生成 Pipe 顺序，`:580` 返回固定顺序；`:595` 仅增加内存复用依赖。
- `schedule_step3.py:74`：官方计算/COPY 时长；`:675` 准备函数读取 Step3 已验证图与顺序。
- `multicore_cut_evaluate_problem_3.py:327`：空 Cache；`:398`：真实 logical key；`:413` 和 `:507`：只由 COPY_IN 填充；`:436`：跨核 release；`:443`–`:474`：固定 Pipe 队首；`:684`：Makespan 取全部操作结束最大值。

## 数值含义

两计划均有1,678个操作、314个 COPY、160个全局唯一 COPY_IN key。旧方案的关键路径下界包含14,974 COPY_IN cycles，新候选为8,618；这两项来自各自不同的关键路径，不能直接把差值当作实际搬运节省。计划的工作量/归核没有改变，收益设想来自加载与计算重叠方式变化。

新下界仍低于旧官方38,390，因此目前不能以该界剔除候选。若新方案成功，最理想也不早于29,780，即相对旧方案改善至多约22.43%；这是乐观上限，不是预期收益。旧方案距自身下界仅1,100 cycles，表明在原顺序内微调的余地相对有限。

## 复现与派工

分析源码 `2b0d7ecbbfaa435492cda65644aae935321de23b`，一次执行：

```sh
uv run --locked --no-sync python -B -m src.q3.static_task_bound_probe results/a/q3-nikolastarx/pipeline-prefix-bound-20260925 --source 2b0d7ecbbfaa435492cda65644aae935321de23b
python3 results/a/q3-nikolastarx/pipeline-prefix-bound-20260925/audit_saved_anchor.py
```

测试入口 `uv run --locked --no-sync python -B -m unittest discover -s tests/q3 -p test_static_task_bound.py -v`：唯一键冷读、重复键乐观命中、COPY_OUT不暖缓存与跨核等待、别名/多端口拒绝、容量与全局环拒绝，5项通过。没有运行官方程序。

源码条件复核委托 Sol medium，软3,500 token/8分钟/至多10次只读工具/0调度或评价调用，不递归派工，实际token不可用。父任务实现下界与读取原件验证。旧已冻结 runner `62c69b20`、manifest与候选plan SHA完全不变；本次新研究提交不要求重跑静态构造或重置评分预算。
