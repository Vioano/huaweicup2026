# Stage K：a053 统一候选加严格结构 H/J

负责人：@yuanzhifang30-sudo；session `yuanzhifang30-sudo/s-0e91469d5b284a0aaf7aca42c456233c`（continue）

分支：`codex/q1-unified-pacing-20260925`；沟通 Issue：[P1 #98](https://github.com/huaweibei123/huaweicup2026/issues/98)、[session #26](https://github.com/huaweibei123/huaweicup2026/issues/26)。

1. **任务目标**：从队长固定 `a0537aeb72dc702af86d67d3194587d581ac207c` 保留全部原候选，在全 PIPE_V、24 轮、每轮 12 条四操作完整链与重复 fork/join 的严格守卫成功时，仅额外构造一个候选：3/4 核为 J paced，5 核为 H startup4 + fused。新候选只参与固定 E1 在线排序；官方未改 E0 Makespan 是外部质量判据，求解器完整冷启动墙钟是独立效率判据。
2. **输入文件**：原始赛题图 JSON、1–5 核、官方固定配置 `data/raw/a/official/data/config.txt`。源码、官方代码、E1 和被复制 H/J 模块逐字节 SHA-256 见 `src/q1_yuanzhifang_stage_k/sources.json`；旧来源中 capacity-return 已属于 a053，不另造候选。原始图在外部以 CLI 参数传入，不进入本分支。
3. **输出要求**：CLI `python -m src.q1_yuanzhifang_stage_k.unified GRAPH --cores K --output PLAN --diagnostics DIAG`。PLAN 恰为 `node_to_subgraph` 与 `core_schedules`；诊断含全部来源、去重/构造失败、实际评分记录、选择原因、参数、接口尝试数、worker PID 可证调用数和无法确认执行的尝试数。stdout 事件在调用前刷新，超时可审计。`cli_body_through_plan_wall_seconds` 只覆盖解析参数之后到 plan close；完整冷启动/收尾墙钟须由外部 runner 测。
4. **限制条件**：原 a053 至多 6 个不同候选；Stage K 至多再加 1 个，故最多 7 个不同计划与 7 次 E1 接口尝试，1 个候选时 0 E1。严格守卫不适用时无新增评分；构造/守卫/在线评分均计入求解时间。E1 固定单 worker、16 MiB cache、单次 60s、启动 10s、worker 最多 7 tasks。接口失败按 captain 首错停止并保留已评分赢家的语义；第一次评分就失败时回退首个原候选，不能称其已有 E1 质量证明。所有失败事件与未知 worker 执行数保留；预算按尝试数保守记账。无暴力枚举或按 case ID/历史成绩分派。E1 排序不是全域无退化保证，最终仍需外部 E0。
5. **验收标准**：来源指纹与固定提交一致；控制器小型注入测试覆盖互斥/上限、原候选、去重、首错回退、身份不符。后续父 P1 监督会话基于队长完整 500 原件制定严格同字节的 100/k4 验证，本卡不授权本线启动真实图 solver、Task compiler、E0/E1 或重跑队长正式 500。
6. **截止时间**：2026-09-25，Asia/Shanghai，本次只冻结可审计源码与准备记录。

## 交付记录

实际命令：`python -m unittest tests.q1.test_unified_stage_k -v`（父现有虚拟环境，Windows；6 tests OK）。

代码提交与输入版本：交付时填写本分支完整 SHA；base `a0537aeb72dc702af86d67d3194587d581ac207c`；H `4f1b9f8be4bbcc98759a19451c108e62e80abb17`；J `aa3f18a71b117ebd0476c8d714c97d8d366d74d7`；E1 `5bfe53a29c1ba05167239f51ea937e602f7f85b4`。

结果与图表：只有控制器测试和来源清单；0 真实图构造、0 Task compiler、0 E0/E1/E2。

结论及限制：新方法最多增加一个结构候选及一次在线评分成本。已有 J 的 051/k3 paced 与 control 对照、H 的 051/k5 事实仅是构造动机，不是 a053 基线对比；队长 a053 真实成绩不能用旧 48fa 结果替代。真实质量与求解冷墙钟均未在本分支测量。原题 5–10 分钟是求解效率建议，不是 600 秒硬淘汰线；有界候选由明确图结构解释而非穷举。

未验证项：真实图上的 H/J 严格守卫、官方 Task 编译与 E0 合法性/成绩、完整冷墙钟、跨 100 用例与 1–5 核覆盖。任何 E1 意外超时的进程树清理由后续受限 runner 负责。

PR：由父 P1 会话整合；本线不创建 PR。
