# Stage F：051/k5 单例，准备阶段

算法 `q1-guarded-split-chain-star / twelve-four-fixed-tail-v1`，作者源码固定 `916a19e57c041ca5dc4aa1f3748e23726464b762`。任务与完整预算见 `tasks/a/q1-yuanzhifang-stage-f.md`。

当前只准备 runner 与导出器，未启动真实 solver/E0。新授权为最多 1 solver + 1 E0、1 worker、30/90 秒、全批 180 秒、0 retry/E1/E2；必须等父会话明确 START，当前 E4 后还有 P2 C 的优先窗口。

旧 Stage C 051/k5 的 253856 周期只引用 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a` 已有原件；官方 singlecore 分母也复用，不新增评价。R=166540 是忽略 COPY/DDR/容量的模型值；不得放入 Makespan 成绩字段。静态重复输入加载分析于实测后生成，不猜测 trace readiness 或唯一耗时归因。

`preparation-checks.json` 记录实际零评分预检。后续 `run/` 只允许首次创建，保留官方 plan/result/trace/log、全部 stdout/stderr、参数/源码/输入身份、UTC、完整 solver wall、独立 E0 wall、失败和调用账。Windows 无 dot_clean，只在本输出范围扫描元数据残留。

准备阶段没有可提交的成功 board feed；实测后导出独立不可覆盖快照，固定 Git 原件预检，再交父研究会话联系成绩台维护者。此目录存在不表示已执行、已上台或已验收。
