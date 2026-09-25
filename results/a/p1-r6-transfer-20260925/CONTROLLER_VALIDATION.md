# 只复用未改变的结构测试

新增可选参数 `--prior-structure-test-receipt`。必须从既有监督原件读到唯一 tests 阶段完成、rc0、无残留、test_process=1；测试代码、branch-aid、官方校验/切图代码及配置SHA逐一相同，而且原始stdout/stderr的实际字节/hash也相同，才跳过tests阶段。源或证据不符时在preflight/任何监督子进程前终止。默认入口仍运行测试。未修改任何构造/评分和原run_stage资源监督语义。

Sol medium执行纯控制器测试命令 `../../.venv/bin/python -B -m unittest discover -s tests/q1 -p test_r6_skip_validated_tests.py -v`：4/4通过，报告0.018秒。源码AST通过；所有run_stage与preflight使用mock；无监督测试child、图构造、Task编译或E0/E1/E2。真实085旧receipt的只读复用门通过，SHA 07e5ea758670bcaea484fd0e78c36f0d65f5365e9750ccf9eb7051cab6ebd910。root审阅diff及四项断言；未重复执行。此记录是作者测试交付与root代码复核，不是四格迁移执行结果。

## 四格单 worker 编排（本次新增）

固定顺序082→075→047→005；720秒总预算、单格180秒、剩余不足180秒不开下一格。heavy/branch/E0各最多4次，E1/E2/重试/新结构测试0次。输入、源、既有测试证明先核；普通结构拒绝/参考字节不符可继续，身份/资源/超时/清理/调用证据失败停止，未运行格保留。异常格消耗不伪报0：成功格小计与全批精确账分开，缺证字段为null，原件路径保留。

主机守卫按协调者最新48GiB主机口径：pressure=normal、观测swapouts不增加、磁盘≥10GiB；不再使用物理空闲≥2GiB。每个子进程前检查，运行时约每秒检查并沿用已有清理路径；源资源读命令有超时，故采样并非实时硬限额，组RSS仍是采样1536MiB停止线。新的freshps文件是外部协调批准的留存入口，控制器只验其存在与hash，不自动证明调度批准或没有其他评分作业；root必须先取得该窗口的明确T0与实际进程复核。

Sol首次mock测试进程因辅助函数错误覆盖TestCase.run，在测试开始前失败；第二次6项中5过1失败，原因为测试夹具只改变返回值而没有改变保存收据，已修正。root审阅后于2026-09-25重新执行一次 `../../.venv/bin/python -B -m unittest discover -s tests/q1 -p test_r6_transfer_batch.py -v`，6/6通过，0.013秒。stdout/stderr原件同目录。预发资源拒绝证明Popen不调用，运行时资源故障以mock验证进入既有cleanup；未启动真实监督child，也未重复旧清理子进程测试。构造/Task/E0/E1/E2实际调用均0。

旧段落中“未修改run_stage资源监督语义”仅指前次6caeddd改动；本次明确增加可选资源回调，其默认None分支保持原行为。四格仍未执行，须另行冻结SHA和获得T0。
