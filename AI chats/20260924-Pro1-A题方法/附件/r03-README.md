# A 题静态结构审计工具

此工具用于将原始 JSON 转换为便于队员和 Agent 阅读、复核的结构统计。
**它不是官方评估器，不输出实际 Makespan，不插入 SPILL，不模拟多核，也不是参赛求解器。**

## 使用

仅使用 Python 标准库，建议 Python 3.10 或更新版本。无需 GPU、网络或 LLM API。

在材料包根目录放置 `profile_graph.py`，然后运行：

```bash
python profile_graph.py data/case_001.json --config data/config.txt --out audit
python profile_graph.py data --config data/config.txt --out audit
```

第二条命令扫描目录中的原始 JSON，跳过名称中含 `_res`、`_trace` 或 `_profile` 的结果文件。每个输入生成一份 Markdown 和一份 JSON，并产生 `batch_summary.json`。解析失败会记录在汇总中，程序以非零状态退出。请将输出目录放在原始 data 目录之外。

## 指标含义

- `compute_ops`：排除 COPY_IN/COPY_OUT 的计算操作数量。
- `full_weak_components`：完整 Op-Tensor 二部图的弱连通分量数量。
- `compute_weak_components`：通过张量桥接得到计算操作依赖图，再排除原始 COPY 后的弱连通分量数量。这些分量没有相互计算依赖，但可能共享输入；不表示通信和带宽相互独立。
- `compute_cycles_by_pipe`：计算工作量，不是实际完成时间。
- `raw_DDR_source_bytes`：原始外部输入张量去重后的体积，不是执行中总读取量。
- `no_L2_resource_lower_bounds`：仅使用计算关键路径、各计算管道总工作量、至少一次输入输出搬运得到的乐观下界；没有考虑同步、资源门控和固定调度器的全部限制，不能解释为可达到的时间。
- `sequential_no_spill_memory`：按文档中的 reverse DFS 顺序，对原始整图执行串行生命周期扫描，在输出已申请、末次输入尚未释放时检查峰值。未验证其顺序与官方源码一致；不做多 Pipe 并行，不执行 SPILL，不代表官方运行峰值。
- `largest_V_component_scalar_cut_diagnostic`：仅作为结构探查，暂时忽略不超过 2 字节张量携带的计算依赖。此阈值是本次样例审计的诊断设置，不是通用推荐切分规则，更不保证所得分组构成合法子图 DAG。

## 已上传样例的复核结果

输入 SHA-256：`fd0b07588473d8b2ce05fab4798808cbc7f60cf1638e05608adc3d62061b8775`

| 指标 | 值 |
|---|---:|
| 操作总数 | 796 |
| 非 COPY 操作 | 667 |
| 张量 | 889 |
| 原始二部图边 | 1899 |
| 完整图弱连通分量 | 16 |
| 计算依赖图弱连通分量 | 36 |
| PIPE_M 计算工作量 | 44610 cycles |
| PIPE_V 计算工作量 | 55496 cycles |
| 忽略搬运的计算关键路径 | 3146 cycles |
| 原始 DDR 输入体积 | 384078 bytes |
| 原始 DDR 输出体积 | 72 bytes |
| 最大单张量 | 16384 bytes |
| 文档 reverse DFS 串行扫描 L1 峰值 | 229376 bytes |
| 文档 reverse DFS 串行扫描 UB 峰值 | 32776 bytes |

计算依赖图中最大的纯 Vector 分量有 133 个计算操作、28759 cycles 的 Vector 工作。将该分量固定在一个核心，必然保留至少 28759 cycles 的 Vector 串行工作，不能仅靠把其他分量分散到更多核心解决。

该分量具有两轮 13 条并行分支、中间标量归约及广播、末端再归约的结构。具体分支和聚合仍以原始图依赖为准，不能改写运算。每轮每条主要分支包含 4 个 268-cycle 操作，总计 1072 cycles；还存在一条 2-op 辅助输入分支和 27 个 13-cycle 的标量操作。

第一轮与第二轮对应分支复用同一份 16384-byte 输入。场景 B 下，可以考虑不同子图同核的跨阶段数据归属；不能直接将前后两个阶段合成一个子图而把中间聚合留在外面，否则可能形成子图依赖环。

## 重要限制

当前没有收到 code 目录里的 Python 源码，也没有完整 data 目录。本包没有任何正式单核或多核成绩。静态分析只能用于提出和淘汰研究假设。

工具不会推断原始 JSON 对应 case_001 或其他用例名；上传后的文件名不是原始用例编号。
