# R5 本地初审：固定同步方案被因果下界排除

输入基点为 `8f2bb73d2479e379945f7e30103c08d7e108bdd7`；本目录为新增的只读审计。原件见 [R5 网页回答](../../../AI%20chats/P1多Pipe链构造证明/RESPONSE_R5_20260925.md) 与 [输出载荷清单](../../../AI%20chats/P1多Pipe链构造证明/附件/MANIFEST_R5_OUTPUT_20260925.json)。本地没有新 Task 编译、响应器调用或 E0/E1/E2 评估。Pro 作者报告的两次模型回放，与本地检查作者保存结果是两件事。

## 已复核结论

| 固定模型方案 | 作者保存 Makespan | 本地观测时长 DAG | 固定签名下界 | DDR 忙碌并集 | 核 0 M/V 重叠 |
| --- | ---: | ---: | ---: | ---: | ---: |
| A：whole_seed | 101836 | 101836 | 101836 | 44604 | 0 |
| B：period7_seed | 109412 | 109412 | 106071 | 72324 | 7804 |

1. [trace 审计](traces/README.md)按 `(Task, Pipe, rank)` 检查全部 FIFO/need 前驱与 Task 门控；两者观测时长 DAG 都与保存 Makespan 相等，未见未解释的起点松弛。半开区间并集/交集复算匹配作者诊断。**这不验证公平 DDR 服务过程**；路径上的 DDR 持续时间超出 solo work 的部分包含整数退休，不能作为拥塞的反事实贡献。
2. [下界复核结果](bounds/result.json)不依赖作者 trace 时长，直接从保存的完整 FIFO/need 签名重建 DAG，并核验 146 个被选 COPY job 的释放下界、服务量与尾长。选中窗口不必全局最强即可给出有效下界；本次没有执行作者枚举窗口脚本。
3. 在指定 Fraction/整数退休模型中，同起点同签名的 m 个核保持同步，相应 COPY 的持续时间至少为 m 倍 solo 服务量。即使尾部另有两个核干扰，三核组仍保持相同服务份额及退休时刻，干扰只能增加竞争。因此 A 的五核公共首轮加三核尾组、B 的三个五核公共轮次加三核/两核尾组均满足所用对称性条件。
4. 若选中 COPY 的最早释放均不早于 r，完成后的必要路径均不短于 q，则这些 job 的全部必要共享服务必在 `[r,T-q]` 内。全局服务能力至多 1，故 `T >= r + sum(m * solo_work) + q`。同核 Task 串行，Task 下界和真实 100-cycle 门控可相加。B 得到 `28364 + 2*34247 + 8913 + 300 = 106071 > 101836`，足够排除这个固定同步 B。

以上不证明 E0 binary64 与 Fraction 一般等价，不验证保存签名来自原图的编译过程，不是整个 P1 或全部切链方案的全局下界。A 恰好达到其固定签名下界，也不等于其所属不切链算法类全局最优。

## 下一步构造的审查

R5 提案保持两计划的 mapping、Task ID、Task 核归属相同，只将独立真实整链 Task 从周期 body 前移到后。完整 body 内的 prefix→return 顺序及尾部 drain 保留。其直接构造的合法性依赖私人真链、无 COPY 桥/跨链依赖、compute 完全覆盖和联合 Task DAG 验证，不能只信调用方传入的链数组。

根代理核对冻结源码：`derive_multicore_plan` 返回排序后的 `subgraph_ids`；`_build_scene_a_tasks` 按此序分配边界 ID，局部 ops/tensors/edges、Step1/2/3 不使用核序。因此在上述条件和相同源配置下，两个核序可复用同一批编译 Task。这里依赖同 ID 同分区的确定性，不依赖尚未普遍证明的跨 ID 缓存等价。新 runner 仍须先运行两份计划的完整结构验证。

仅准备一个受限机制控制对：固定 q=7、s=3 和已保存 body 周期 35405，真实整链 work=4512；从结构识别结果构造，不向统一 solver 加 case 编号分支。预期 53 个唯一 Task，一次静态编译、两次最多 30 秒的 Fraction 响应、单 worker、0 retry、0 E0。仅当错相版胜控制且突破条件性不切类下界 99264，才建议另行安排官方验证；失败不扫描相位或包宽。

**这仍是未评分提案。** 本轮统一算法的官方全量五核均值仍为 4.025907473836023；不将只读证书、作者模型值或单例改善提交为新的统一全量成绩。用户要求本轮取得显著提升的统一全量官方 Benchmark 后暂停；当前尚未满足。

## 可复核命令

```sh
python -m src.review.p1_saved_signature_window_audit --output /tmp/new-r5-bounds.json
python -m src.review.p1_saved_trace_interval_audit --audit-dir results/a/p1-r5-local-audit-20260925/traces --output /tmp/new-r5-intervals.json
```

使用尚不存在的输出文件；脚本拒绝覆盖。输入签名 SHA-256 固定为 `2a90a5b0e8b3ff19fe88a07e6580dc4899a63b7654d0d268c0941b947549c95b`。审计为纯 JSON 算术；这些命令不调用官方评分或模型模拟。新机制 runner 的五项合成/fake 测试另外在项目锁定 Python 3.12.13 环境通过，不代表真实图编译或运行通过。
