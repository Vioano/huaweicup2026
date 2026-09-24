# 079计算空隙的官方依赖重建

目标是解释已有时间线中90,146周期退化，而非生成一份新成绩。读取固定原079图、原forest500计划及新band-pair计划、各自已完成P3原件；源码与输入先冻结。使用未修改官方 `_build_scene_b_tasks` 重建两份运行时图，逐核核验op覆盖、Pipe完整次序、Step3内存补边数量和搬运统计与已有原件一致。对每个PIPE_M操作，核验实际start是否等于前一M结束与全部真实前驱结束的最大值；再给每个正间隙标出达到该界的原始数据边/内存复用边。

这是调用官方预处理，不是纯文件解析：**最多2次整图Task构造、10次核内Step3模拟**；0新多核P2/P3模拟、0solver、0retry，1worker、每份90秒、整批180秒。失败即停，保留调用账和日志。程序不删内存边、不改官方代码、不把已有Cache时序用于生成新官方成绩。

来源：`band-mechanism-20260925/run.json` 的079-pair与固定 `bff88a66cd76ceb2d75242bf99d34bfe8b1879d4` 的forest500收据。输出在独立 `memory-dependency-audit-20260925/`。执行：`uv run --locked python -m src.q3.memory_dependency_audit results/a/q3-nikolastarx/memory-dependency-audit-20260925 --source FULL_COMMIT --forest-root FOREST_PRODUCER`。

验收边界：紧约束的内存边可说明冻结运行时图中某次发射为何不能更早；删除它再套旧时长不证明新的合法方案可达。更改提交顺序会同时改变Step2重载、Step3虚拟额度来源和共享Cache时序，必须另冻结新构造后用官方完整评价验证。不得将条件反事实当作新的M成绩、普遍定理或泛化证明。
