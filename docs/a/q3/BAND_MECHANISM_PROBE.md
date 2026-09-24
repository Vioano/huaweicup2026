# 蛇形分带分核与树序的最小因果检查

动机：已冻结的输入复用族31份评分只有4份M改善、22份退化。Pro R4给出了更小的输入覆盖D及受限L1树序模型，但它未运行真实JSON或E0，故先核可证伪机制，不扩大到全500。

1. **目标**：在058/079、5核上区分整树归核和核内树序的作用，分别记录官方M、extra COPY、spill、字节命中率与同计划P2/P3；D是逻辑输入覆盖，不是官方物理DDR或M。
2. **输入**：固定原图、官方源码/配置。两图均已见；新归核由完整Cartesian结构和两轴蛇形分带配额DP确定，不按case ID选算法。新归核固定后，分别保留原component-ID树序，以及在声明的双组原子驻留模型下优化端点的树序；每树DFS、原op与张量端口不变。
3. **输出**：`src/q3/grid_band_dp.py`、`forest_band_dp.py`、`band_mechanism_probe.py`，以及新目录中的4份精确plan、8份原版E0输出、参数/源码/输入/输出SHA及调用账。Pro附件和静态复核见 `AI chats/20260924-Pro-P3-归约森林切分/`、`results/a/q3-nikolastarx/pro-r04-independent-20260925/`。
4. **事前预算**：2图×2树序×P2/P3，最多8次E0，单worker，单次90秒，全批360秒包含预检、构造与收尾；0 solver、0重试，首次失败即停。沿用与其他本机P2任务各1worker的约定，不改其进程/目录。无新服务、无云资源。控制程序在第一次E0前保存全部plan；必须固定提交、真实图结构guard和必要测试通过后执行。
5. **验收**：两个树序必须逐核拥有相同原树集合；方案只有官方两字段；P2/P3读取完全相同plan；每份结果保留成功/失败及SHA；复核原件，输出正负结果。原forest与旧轴构造结果仅作为已有测量的控制，校验其plan与来源后比较；旧数据不是本批新E0，不能拼成新统一求解器全500成绩。构造墙钟与外部E0墙钟另列，均不称完整solver wall。
6. **决策**：新D更低但M不低则接受反例，定位实际COPY/spill/时序，不为了证明代理而换对照。若有明确收益，再冻结泛化规则及在线预算；无论两图结果如何，本批不证明泛化或整体最优。对于079，已复核的D最优只适用于给定配额的完整等权Cartesian整树模型。

执行入口：

```sh
uv run --locked python -m src.q3.band_mechanism_probe results/a/q3-nikolastarx/band-mechanism-20260925 --source FULL_COMMIT --preflight
uv run --locked python -m src.q3.band_mechanism_probe results/a/q3-nikolastarx/band-mechanism-20260925 --source FULL_COMMIT
```

原模型DP只在连续行带、交替列扫、沿序固定配额切段的族内精确；两轴比较为 `O(kmn(m+n))`，不是一般分区全局求解。另一个树序目标假设原子组驻留，与官方逐张量容量/Belady驱逐及共享FIFO L2不同，必须由这组实验判断外推是否有效。
