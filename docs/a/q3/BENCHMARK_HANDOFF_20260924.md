# Q3 最高优先级稳定候选：跨平台语义复核

仅向成绩台调度 session s7c98 提交，由其统一给 LYX/farmer 排队；本文件不是直接给两位同时派单，
也不扩大正在运行批次。P3 算法写范围仍归 session 3172。首选小而有区分力的5格，不重复500格矩阵。

## 固定身份与目的

- 算法与runner：`6389818b1028ada74c685483dd1cd75fb8e16285`，`src.q3.guarded_solve`、`src.q3.feedback_benchmark`。
- 官方源码集合 SHA-256：`de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0`。
- config SHA-256：`dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。
- 全部输入逐图SHA与实际固定源码哈希在既有 `guarded-20260924/run/batch.json` 对应格中；输入原件只读。
- 本机控制原件提交：`11bd277697839b14f513bdb3e38cf7a4d43d913a`，
  `results/a/q3-nikolastarx/guarded-20260924/` 的完整34成功候选与20最终结果。
- 目的：Windows/另一台机器上独立确认严格选择、剪枝、森林/word回退行为和最终官方数值；
  不把墙钟跨硬件相除当算法效率改进。此为验证候选，不预称对方复现成功。

| case/k | 预期最终官方cycles（待对方核） | 预期在线E0 | 验证理由 |
|---|---:|---:|---|
|002/3|93527|1|提案严格下界94428被剪，未评分plan/hash保留|
|062/5|588101|2|最大单树，anchor673177后接受release|
|063/5|232381|2|另一单树尺寸，anchor336337后接受release|
|080/4|83124|1|未切分多树守卫保旧交错，spill229376仍合法|
|008/5|52291|1|resource-word守卫外保持既有算法|

## 运行与预算

使用上面的**算法提交**新建自己的验证worktree；不要在研发owner的目录执行或改源码。
`uv sync --locked` 后，从本交付提交提取
`results/a/q3-nikolastarx/guarded-20260924/benchmark-request-5cells.json` 到该checkout（它是未跟踪的运行输入）。
目标队员在首次运行前只填本人实际 `producer_session`、新 `runtime_id`/run ID，不改变算法、输入、
次序或限制，并保存自己实际manifest；不能伪装为队长机器或沿用队长session。
取文件请保留UTF-8原字节，不使用可能写UTF-16的旧PowerShell重定向。

```sh
uv run python -m src.q3.feedback_benchmark results/a/q3-nikolastarx/guarded-20260924/benchmark-request-5cells.json results/a/q3-verification/NEW_RUN
uv run python -m src.q3.board_export results/a/q3-verification/NEW_RUN/batch.json results/a/q3-verification/NEW_FEED.json
```

这是唯一一批5job，最多10次新E0、1 CPU worker、每job90s、整批600s，预期实际7次E0；
无GPU/Colab、无随机搜索、无重试、无新单核分母或P2评分。线程/冷缓存/RSS实测才填，否则null注明。
已有全部8个单核原件及来源可复用，固定图/config/official/hash匹配后附到feed，不能重跑分母。

首个异常、超时、源码漂移、非法计划、结果不一致或证据hash问题停止后续dispatch，
保存原 stdout/stderr/plan/result/ledger；向成绩台owner和算法owner回报具体差异。
成功不自动扩成15格或500格；只有发现可定位的平台/数据类型差异，或新算法机制需要覆盖时，
另定义有限复核范围。未开始的请求可以由owner排队，不需要占用资源空跑。

## 输出与当前状态

每格保留最终两字段plan、所有实际评分候选的完整E0 gzip、未评分剪枝plan/hash、receipt、
真实argv、实际机器/解释器/依赖/输入身份、启动至退出wall及逐次调用状态；完整正负feed发布到本人分支。
请比较官方字段值/类型及计划身份，若官方中非确定性诊断字段存在差异逐字段记录，不能静默归一化。

本机已20job/34E0完成并封存，无在途评分；本请求尚未发给成员、尚未对方开跑。
051/024/016阶段分叉归约的新方法此时仅静态研究，不在此稳定候选内，成熟后另交调度owner，避免并行抢写。
