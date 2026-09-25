# 只复用未改变的结构测试

新增可选参数 `--prior-structure-test-receipt`。必须从既有监督原件读到唯一 tests 阶段完成、rc0、无残留、test_process=1；测试代码、branch-aid、官方校验/切图代码及配置SHA逐一相同，而且原始stdout/stderr的实际字节/hash也相同，才跳过tests阶段。源或证据不符时在preflight/任何监督子进程前终止。默认入口仍运行测试。未修改任何构造/评分和原run_stage资源监督语义。

Sol medium执行纯控制器测试命令 `../../.venv/bin/python -B -m unittest discover -s tests/q1 -p test_r6_skip_validated_tests.py -v`：4/4通过，报告0.018秒。源码AST通过；所有run_stage与preflight使用mock；无监督测试child、图构造、Task编译或E0/E1/E2。真实085旧receipt的只读复用门通过，SHA 07e5ea758670bcaea484fd0e78c36f0d65f5365e9750ccf9eb7051cab6ebd910。root审阅diff及四项断言；未重复执行。此记录是作者测试交付与root代码复核，不是四格迁移执行结果。
