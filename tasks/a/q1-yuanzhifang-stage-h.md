# P1 Stage H：四核首轮与归约子树融合

负责人：@yuanzhifang30-sudo；实测 session `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`。分支 `codex/q1-wave-benchmark-yuanzhifang-20260924`，父研究会话沿 [Issue98](https://github.com/huaweibei123/huaweicup2026/issues/98) 汇总通信；子会话不写中央成绩台。

1. **任务目标**：仅真实051/k5，分别检查首轮四核降低DDR并发、完整归约子树融合减少小COPY/尾工作两个有限机制。算法族 `q1-guarded-intact-prefetch`。`four-core-start-v1` 使用 `--startup-cores 4`；`four-core-start-subtrees-v1` 另加 `--fuse-reductions`。两者首轮3/3/3/3/0、后续4/2/2/2/2，尾核0，预期143Tasks，selected=`intact-prefetch-frontier`；模型R分别208152/206917，不是E0成绩。
2. **输入文件**：作者固定 `4f1b9f8be4bbcc98759a19451c108e62e80abb17`，五源码依赖 prefetch_frontier/star_frontier/fork_frontier/construct/diagnose，按固定Git字节取材，不合入父全E4产物。051图SHA256 `884e8b12ac1f7a9b569958909680e8c2f6055966a59c9f929ffd5cee48aae43b`；config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`；十个冻结官方源严格原字节校验。仅复用C `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a` 的253856、G `45fde88569b4ce877bda397ae32bc9a1b4abf082` 的234536原件，全部输入身份/计划/结果hash复核，0旧方法重跑。
3. **输出要求**：独占 benchmark_h.py/export_h.py、本卡与 `results/a/q1-yuanzhifang/stage-h-20260925/`。新run目录只创建一次，每variant独立方案、诊断、完整官方result/trace/log及stdout/stderr/run；保留完整调用账、所有失败、UTC、环境/资源、输入/源码hash。冷solver从新进程读取输入到方案及诊断落盘退出全程计时；外部E0另列。导出逐variant比较CSV、DDR/重复输入分析与标准feed，固定Git原件预检后交父发布。
4. **限制条件**：新预算最多2冷solver+2外部未改E0、1worker，solver30秒/E090秒、全批360秒、0retry/E1/E2，每variant一次。旧批预算封存。预期timeout/领域合法性失败保留继续，身份/输入/监督/磁盘故障停批；诊断selected/variant/flags/143Tasks/R异常不启动E0。原始数据、作者与官方源码不可修改。不在线挑选两者赢家冒充单一算法。
5. **验收标准**：准备期0solver/E0/Task compiler/全图扫描；提交runner供父审阅并待明确START/token。依赖与输入预检、两字段plan、实际依赖/容量由唯一E0验证；成功feed引用同一提交原件且eligible，失败保留。父报告3合成测试0.600秒，含平衡/梳状归约、1/2/24轮、覆盖/完整链/联合无环/手算R，不替代真实冷solver。DDR服务量和 `sum(max(1,ceil(bytes/60)))` 是容量1的必要Makespan下界，不能当精确E0、不能与gate直接相加、不能假定COPY串行独占。静态重复输入量不唯一解释时间因果。
6. **截止时间**：北京时间2026-09-25父协调资源后执行；现只准备，无自动开跑或预算扩大。共享资源只承诺本批1worker，不称物理主机独占。

准备：`python -X utf8 -B src/q1_yuanzhifang/benchmark_h.py --graphs GRAPH_DIR`；START后追加 `--execute --window-token PARENT_START_REFERENCE`。导出：`python -X utf8 -B src/q1_yuanzhifang/export_h.py --graphs GRAPH_DIR --output results/a/q1-yuanzhifang/stage-h-20260925/board-feed-UTC-stage-h.json`。本地/固定Git预检：`python -X utf8 -B src/benchmark_board/protocol.py FEED --submission [--commit FULL_SHA]`，不执行评价。

复用本session已uv sync --locked的独立环境，43.79秒初始依赖成本在A前记录，完整研发耗时未知。官方5–10分钟是效率建议，30/90/360秒是本次实验预算。按已亲自读取的协议5e626d86与磁盘规则2922eb14，单格两个参数变体只作暴露研发对照，不代表统一版本100×1–5核主成绩或达成均值2.19150/2.83820/3.42710/3.90660。历史赢家拼盘不能充当路线胜负证据；协议不追加全量预算。未运行Pro附件，未把Pro限定模型当官方语义或实测。
