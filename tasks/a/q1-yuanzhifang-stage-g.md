# P1 Stage G：整链根核预取单例证伪

负责人：@yuanzhifang30-sudo；实测 session `yuanzhifang30-sudo/s-57863f3c1318476ab027cd8a1338c117`。
分支：`codex/q1-wave-benchmark-yuanzhifang-20260924`。沟通：[Issue #98](https://github.com/huaweibei123/huaweicup2026/issues/98)，父研究会话汇总外发，子会话不重复联系成绩台。

1. **任务目标**：仅真实 051/k5，证伪或支持保留四节点重链、利用根核早900周期释放进行预取的构造假说。首轮整链分配3/3/2/2/2，后续4/2/2/2/2，尾核固定0。算法 `q1-guarded-intact-prefetch`，variant `fixed-root-four-two-v1`，预期 selected=`intact-prefetch-frontier`、144 Tasks、R=208152；模型值不是官方成绩。比较已有 C 的253856周期/9438614B调度搬运，不重跑旧方法；F负结果保留封存。
2. **输入文件**：父作者 `src/q1_yuanzhifang/prefetch_frontier.py` 固定 `e29685da0268420f2d881246603763d6bf8baf5b`。源码依赖必须包含 prefetch_frontier、star_frontier、fork_frontier、construct、diagnose；十官方源全部固定校验。官方051图 SHA-256 `884e8b12ac1f7a9b569958909680e8c2f6055966a59c9f929ffd5cee48aae43b`，config `dcd10de54b23f8366428fb24e828812b1da9549e6eae4a3c3f38604fe5ae77b9`。C原件固定 `88e95e28f6b6fdfe7e4d0b91a7b124740dc5006a`，仅此已暴露研发单格，无盲测声明。
3. **输出要求**：独占 `src/q1_yuanzhifang/benchmark_g.py`、`export_g.py`、本卡及 `results/a/q1-yuanzhifang/stage-g-20260925/`。新 `run/` 首次创建、拒绝覆盖，记录参数/源码/输入hash、环境/资源、UTC/调用账、本轮cold solver与外部E0各自wall、两字段plan/诊断/全部官方result/trace/log/stdout/stderr/run与所有失败。原结果无损保全；导出比较CSV、静态DDR/重复输入分析及不可覆盖标准feed，固定Git字节预检后交父统一发布。
4. **限制条件**：本轮新预算最多1冷solver+1未修改外部E0，1worker，solver30秒/E090秒/全批180秒，0retry/E1/E2；不重开F，不挪旧批额度，不重跑单核或C。源/身份/输入/监督/磁盘异常停批；失败和负结果保留。核对cold输出selected/144Tasks/R208152，异常不启动E0；容量及实际合法性由唯一外部E0复评。预检与研发产物不能冒充solverwall，原始数据只读，作者和官方源码不可改。
5. **验收标准**：准备期0solver/E0/Task compiler、0全图扫描；完整源码SHA和runner提交后供父审阅。已核输入、十官方源、五算法依赖和旧C同身份原件，真实进程到方案/必要诊断落盘并退出计求解wall，E0另列。资源窗口必须由父明确START并写token；只用1个P1worker，不承诺物理主机独占。所有成功/失败进入账本，成功feed同提交原件一致且eligible；静态COPY数量不当作完整耗时因果。单例不代表100图均值，也不证明达到2/3/4/5核均值2.19150/2.83820/3.42710/3.90660。
6. **截止时间**：北京时间2026-09-25按父协调；作者已固定SHA，当前只准备，等待父审阅runner与明确START。没有任何自动预算扩展或空闲自启动。

准备命令：`python -X utf8 -B src/q1_yuanzhifang/benchmark_g.py --graphs GRAPH_DIR`，源码未冻结时明确拒绝。
START后同命令追加 `--execute --window-token PARENT_START_REFERENCE`。
导出：`python -X utf8 -B src/q1_yuanzhifang/export_g.py --graphs GRAPH_DIR --output results/a/q1-yuanzhifang/stage-g-20260925/board-feed-UTC-stage-g.json`。
本地及固定Git预检使用 `src/benchmark_board/protocol.py FEED --submission [--commit FULL_SHA]`，不写中央服务、不执行评价。

复用本 session 已 `uv sync --locked` 的独立环境，实际锁文件hash记录在environment。官方5–10分钟是效率建议；30/90/180秒是本次实验预算，非原题淘汰线。Stage G 目前没有正式成绩；source/runner固定、执行、生产方格式通过、维护者接收/上台、科学验收分别记录。

作者固定提交提供的合成测试由父报告：2个测试、包含两种归约树与1/2/24轮、独立手算/联合环/完整链/重编号/回退，0.273秒；0真实图solver/E0。生产者已阅读源码、测试与 `PREFETCH_FRONTIER.md`，不重复运行构造测试占评分窗口。官方DDR为活跃COPY共享总带宽；只允许以总字节/总带宽作必要容量界，不能把各COPY独占服务时长和当作共享处理的必需墙钟。

零评分预检已通过：五算法依赖、十官方源、051/config与旧C同身份原件；静态旧计划重复外部输入9043968B和官方分区搬运一致。preparation-checks记录19.948239秒准备成本（含硬件清单），不是求解wall。真实solver/E0/Task compiler及全图扫描仍全部为0，run目录未创建。
