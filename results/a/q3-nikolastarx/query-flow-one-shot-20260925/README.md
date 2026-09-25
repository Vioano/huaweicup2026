# R8 唯一071/K5候选官方机制预算（尚未运行）

候选来自query-flow-static-repair-20260925/run/case_071_multicore_res.json，SHA256 b0ccb1c9d9e2f90ae6566ecaa725a0440c47d942401a3cdcb261d90eb0968136；原071 SHA437cc74cae9e0fc0cb89b05403c62062ceff8d5bc2224c8834c519e69524e897，固定官方源码集合de11a83db8d7c47ed328b15a7df71d613a833b16cd23ee9fe877999578a1ace0/config由source-manifest逐字核验。预算与计划/runner先提交冻结，再申请共享资源准入。

假设：跨现有模块共同定query-flow owner降低完整计算图往返，从而在真实COPY/DDR/Cache下仍降低官方Makespan。已知本地模型下界4538<旧官方计划计算下界5441，但旧官方M=7782，差额不等于可消除通信时间。

执行：`python3 -m src.q3.query_flow_probe results/a/q3-nikolastarx/query-flow-static-repair-20260925/run results/a/q3-nikolastarx/query-flow-one-shot-20260925/run --source <本包完整冻结SHA> --plan-sha256 b0ccb1c9d9e2f90ae6566ecaa725a0440c47d942401a3cdcb261d90eb0968136 --admission-ref <实际调度准入记录>`。

最多1个新P3 E0，只有M<7782且准备guard全通过才1个同计划P2 E0（所以总最多2E0，绝非旧044预算续跑）。1worker，每阶段90秒、全批600秒，首异常停，0重试；worker自身90秒墙钟timer，父进程超时只杀自己的进程组。全量benchmark未批准。无独立prepare调用：仅在该次P3构建Task的返回点用观察器保存原Task和Step2中间件、核验再继续。正常每P3/P2各1Task、每Step1/Step2/prepareStep3/step3_simulation各5；调用开始先记账，失败耗预算。

准备guard：每核物理tensor ID/pos/size与原tensor touched规则严格一致（DDR本地视图UB）；唯一局部producer、全池总支持不超固定容量；Step2无spill、Step3无MEMORY_REUSE；原compute owner和每pipe序与计划相符；原tensor源/目的Task独立公式与真实COPY字节一致。先保存完整原件再判断；任一异常停，不改计划重试。

结果同时记录M、extra/spill、字节hit、条件P2/P3同计划G；观察器和评价诊断墙钟单列，solver_wall_seconds=null。它只是机制实验，不是固定算法全500，也不宣称跨平台或隐藏集泛化。新算法有官方正证据后才由统一调度决定冻结统一入口和最有价值的全量验证。用户要求本R8轮后暂停，不启动R9。
