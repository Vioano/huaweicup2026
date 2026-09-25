# 固定方案 COPY 下界：两份旧原件复核

目的：核查 044/046 容量流水线的剩余空间，避免把可见 COPY 等待误当成可以任意
预取消去的时间。算法证明、适用守卫和局限见
[`SINGLETON_COPY_BOUND.md`](../../../../docs/a/q3/SINGLETON_COPY_BOUND.md)。
这是新的静态下界实现及旧原件核对，**不是新算法性能成绩，也不提交成绩台 feed**。

| 已有五核计划 | 旧计算下界 | 新 COPY 下界 | 官方 M | 固定方案余差 |
|---|---:|---:|---:|---:|
| 044 capacity | 26842 | 37194 | 38390 | 1196 |
| 046 capacity | 74990 | 80800 | 82505 | 1705 |

核对 044 的 182 条、046 的 146 条虚拟首次 COPY 与保存的官方时间线：原 key、
最早消费桶、COPY 时长下界、消费者等待、跨核释放及桶间固定 FIFO 均通过。
其中分别有 61、58 条独核外部输入首次 cold 断言，也与原件一致。
基线原件来自 `pipeline-capacity-two-shot-20260925`，计划/结果哈希在脚本中固定，
图/配置/官方代码对原批 manifest 核验；新代码和本脚本 SHA 写入 `summary.json`。

这给出**固定计划松弛**的时延余差上限，并没有证明某个合法新计划能达到该界。
跨计划更换切点、归核、bucket 顺序以后，旧界不能直接沿用。算法目标仍是新的
同算法全 100×1–5 核表现，不能拼接本表与 forest 全量历史成绩。

实际命令：

```sh
PYTHONDONTWRITEBYTECODE=1 uv run --locked --no-sync python -m unittest tests.q3.test_singleton_copy_bound -v
PYTHONDONTWRITEBYTECODE=1 uv run --locked --no-sync python results/a/q3-nikolastarx/singleton-copy-bound-20260925/reproduce.py
```

5 个测试方法包括同桶不能错误累加服务的反例、逻辑 key 别名反例和守卫。
初次只读复核因官方配置解析器要求声明 `problem_3` 全部字段而提前退出；修正
参数清单后完成两份结果核验。没有失败的 E0 或隐含重跑。另有一次未落盘的
两图静态数值预读用于判断本界是否有价值，未调用官方 Task/评价。
本轮新 E0=0，solver=0，Task=0，Step3=0；未获得本机 smoke 资源窗口，既有
capacity 2-job manifest 保留未开始状态。数学审查由 Sol 完成、根代理复核并
实施全图 alias 拒绝和显式配置参数；不是独立官方复跑验收。
