# R6 官方准备与 P3 单次机制实验：已冻结，未启动

## 目标、输入、产物

验证本地静态复现的 044/5 核首批合桶方案，在未修改官方执行图中是否真的保持共享输入前缀、无内存复用阻塞、零 spill；仅在全部检查通过后，用一次 P3 检验相对旧容量方案 Makespan 38,390 的变化。图、配置、两字段计划及哈希固定于 `manifest.json` / `freeze-check.json`。

完整源码/runner 提交：`62c69b20ab887c76567dbab5fcce6eef30107b5c`。静态构造的原始来源仍为 `fc73b341693d9c3002aa3aa01f1f5de170537ae6`，已记录的全部源文件及原始输入哈希与新 runner 树一致，因此不为新增监督器重复构造。Manifest SHA：`b2ec66eb5e4e0777519c09a3f8937e5df514e1fc6372e1a88e3aa369af9c9a14`。

产物为完整 Task/Step1/Step2/Step3 准备原件、检查项、实际调用收据、完整官方 P3 gzip JSON、stdout/stderr、外部资源采样与失败记录。它是一个已见开发图的机制实验，不是新版完整求解器，也不向成绩台拼入单一算法全量结论。

## 预算、停止条件与验收

| 阶段 | 官方入口 | 最大调用 |
|---|---|---|
| 准备 | 原版 P3 `_build_scene_b_tasks` | 1 次，内含 Step1/Step2/prepare-Step3 各 5 次；冻结 prepare-Step3 每次运行一个 Step3 模拟 |
| 评分 | 原版 `evaluate_problem_3`，经原 `src.q3.oracle` main | 最多 1 次，另含 Step1/Step2/prepare-Step3/Step3 模拟各 5 次，逐 code-object 观测计数 |
| 不运行 | P2、候选搜索、统一 solver | 0 |

一名 worker，两阶段串行；各阶段 60 秒、整批 120 秒，子进程组 RSS 512 MiB，0 重试。准备成功且完整依赖检查通过才允许评分。先逐阶段预留调用额，失败或中断后不自动释放/续跑；评分 worker 有独占 claim 防止重复消耗。旧 da1 smoke 及其他批次预算均不借用。

启动必须另有总调度给出的本机独占窗口引用；`--admission-reference` 只是留痕，不会自动取得授权。启动前两次采样均需 macOS pressure=1（Normal）、unused≥1536 MiB、Swapouts 不增长。运行时压力非 Normal、unused<1024 MiB、新 Swapouts、子进程组 RSS 超限、到期或监测异常即终止自己创建的进程组并 wait，保留日志；不触碰别的 session。

资源和时间监督是采样式的，`top`/`sysctl`/`vm_stat`/`ps` 各有有界超时；到期检测可能晚一个采样周期，终止回收另计。不是内核硬内存上限或精确实时截止。官方函数没有替换；Python profile 仅观测调用/返回并保留中间原件，但增加诊断墙钟开销，不能把本批耗时冒充求解器性能。

验收以原件为准：完整准备图通过全局合法性、Step2 零 spill 且原字序不变、下游 MTE2 前缀相同且没有外部/复用依赖进入前缀。随后才报告 P3 Makespan、额外搬运及字节命中率；无 P2 配对，因此不报告 CacheGain。失败也是实验结果，不为达成正收益改计划或重试。

## 运行交接（资源窗口尚未取得）

在源码提交 `62c69b20ab887c76567dbab5fcce6eef30107b5c` 的独立干净 checkout 执行。因为 manifest 是后续交付材料，不能直接在较新的交付 HEAD 冒充该运行版本；从本交付固定提交取出 manifest 到该 checkout 的同名结果路径，原始 044 图按来源哈希准备，使用项目锁定 Python 3.12 环境。运行前 `verify_source` 会验证实际 HEAD、源码/官方配置、原图和依赖锁。

```sh
python -B -m src.q3.pipeline_prefix_probe \
  results/a/q3-nikolastarx/pipeline-prefix-probe-20260925/manifest.json \
  results/a/q3-nikolastarx/pipeline-prefix-probe-20260925/run \
  --manifest-sha256 b2ec66eb5e4e0777519c09a3f8937e5df514e1fc6372e1a88e3aa369af9c9a14 \
  --admission-reference '<总调度的本次窗口引用>'
```

当前只做了 manifest/原件/运行源码的只读 freeze-check，没有启动监督器、prepare 或 P3。4 个 runner 合成测试通过（第一次测试夹具因 macOS `/var` 与 `/private/var` 未规范化导致 2 项失败，修正夹具后全部通过）；模拟了资源门关闭、监测失败清理、旧静态来源复用与哈希/预算拒绝。没有真实故障注入或跨平台验收。

## 派工及下一步

静态边界测试用 Sol medium（软 4,500 token、10 分钟、0 官方调用）；监督器实现用 Sol medium（软 6,500 token、12 分钟，后续小修软 1,000 token、2 分钟，0 官方调用）。不支持硬 token 限额，实际模型用量不可见。作者负责构造与筛选；窗口取得后冻结命令执行和导出可交 Luna medium，不临时改算法。新批次由总调度排程，作者保留 runner/结果写权。无硬日期截止，当前等待资源而非等待额外 Pro 问题。
