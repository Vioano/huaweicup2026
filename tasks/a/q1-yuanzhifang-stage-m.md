# Stage M：相邻 Task 合并机制小试

负责人：@yuanzhifang30-sudo

分支：`codex/q1-adjacent-union-20260925`

沟通 Issue：https://github.com/huaweibei123/huaweicup2026/issues/98

1. **任务目标**：在冻结的 shared-input 构造结果上，对相邻 Task 尝试满足 resident-union 容量证书的合并；只在诊断确认至少一对真实合并后调用官方 E0。此单格用于验证机制是否触发及其真实 E0 质量，不代表全矩阵均值或算法普遍收益。
2. **输入文件**：官方只读 `case_044.json`、官方固定配置与源码；输入身份由冻结 source manifest、完整官方源码聚合哈希及 graph/config SHA-256 核验。固定上游为 `a0537aeb72dc702af86d67d3194587d581ac207c`，本方法冻结为 `6003ef7684c5649b5ccafb653c4b11aa67945439`。
3. **输出要求**：独立目录 `results/a/q1-yuanzhifang-stage-m/stage-m-20260925/run/` 保留 raw plan、diagnostics、solver/E0 stdout、stderr、process event、run receipt、E0 result/trace/log 与批次清单；`export_m.py` 生成一个 submission-v1 feed，不运行评分。对照固定单核 A 原件 `6fcec11ccc472a1a652b21feb6fccf85a4555598`；v4 的 044/k2=64624 只作历史参考。
4. **限制条件**：只运行 044/k2，一次 cold solver、至多一次未修改 E0；0 E1/E2/retry、1 worker；solver/E0/全批上限 60/60/180 秒；启动和运行前可用 RAM 均至少 1 GiB；每个 Windows Job 的提交内存硬上限 512 MiB。只有 `diagnostics.selected == "adjacent-union"` 且 `merged_pairs` 非空才运行 E0，否则保存一次 solver 原件并记 `mechanism-not-triggered`。监督/身份错误停止，不调参、不重跑。设置 `PYTHONDONTWRITEBYTECODE=1`，防止子 Python 改写官方原件目录。执行必须同时带父级 START token 与本会话 producer-session。
5. **验收标准**：父级明确 START 后检查 runner preflight、预算及输入身份；执行后核对每个原件哈希、诊断选择和合并对、真实 solver/E0 wall 与调用账。成功或未触发均按事实导出；不得把机制代理、历史分数或单格结果写成全量均值。未启动前仅作源码/AST/身份预检。
6. **截止时间**：按队伍短窗口安排，Asia/Shanghai。

## 交付记录

实际命令：准备阶段仅运行只读 `python -m src.q1_yuanzhifang_stage_m.benchmark_m --graphs <官方图目录> --preflight`；实际运行命令须记录在启动后的收据。

代码提交与输入版本：runner/export/job 与本任务卡独立提交；构造源码固定为上述 SHA。

结果与图表：尚未 START；预定输出位置如上。

结论及限制：这是 044/k2 单机制试验，不对全量题目或 Makespan 改善作先验承诺。

未验证项：真实图上的构造、合并是否触发、官方 E0 成绩及墙钟均待 START 后确认。

PR：待固定提交后按协作流程登记。
